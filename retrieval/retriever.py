"""
检索模块 - 支持词法检索、向量检索与混合检索
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from core.logger import get_logger
from retrieval.bm25 import BM25LexicalScorer, tokenize_text
from retrieval.embeddings import create_embedder
from retrieval.reranker import EvidenceReranker
from retrieval.vector_store import SQLiteVectorStore

logger = get_logger(__name__)


class Retriever:
    """
    代码检索器
    
    职责：
    1. 接收 chunks 列表和查询
    2. 计算相似度
    3. 返回 top-k 最相关的 chunks
    """
    
    def __init__(
        self,
        chunks: List[Dict[str, Any]],
        top_k: int = 5,
        workspace_root: Optional[Path] = None,
        backend: str = "hybrid",
        vector_db_path: Optional[Path] = None,
        embedding_provider: str = "hashing",
        embedding_dim: int = 384,
        vector_candidates: int = 20,
        lexical_backend: str = "bm25",
        bm25_k1: float = 1.5,
        bm25_b: float = 0.75,
        rerank_enabled: bool = False,
        rerank_top_n: int = 10,
        ollama_embed_model: str = "embeddinggemma",
        ollama_embed_api_base: str = "http://localhost:11434",
        ollama_embed_timeout: int = 30,
    ):
        """
        初始化检索器
        
        Args:
            chunks: CodeChunk 字典列表
            top_k: 返回的最相关 chunks 数量
        """
        self.chunks = chunks
        self.top_k = top_k
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None
        self.backend = backend
        self.lexical_backend = lexical_backend.lower()
        self.rerank_enabled = rerank_enabled
        self.rerank_top_n = max(top_k, rerank_top_n)
        self.vector_candidates = max(top_k, vector_candidates, self.rerank_top_n)
        self.embedder = create_embedder(
            provider=embedding_provider,
            dimension=embedding_dim,
            ollama_model=ollama_embed_model,
            ollama_api_base=ollama_embed_api_base,
            timeout=ollama_embed_timeout,
        )
        self.bm25_scorer = BM25LexicalScorer(self.chunks, k1=bm25_k1, b=bm25_b)
        self.reranker = EvidenceReranker() if rerank_enabled else None
        self.vector_store = SQLiteVectorStore(vector_db_path) if vector_db_path else None
        self.collection_name = self._build_collection_name()
        self.logger = get_logger(__name__)
    
    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """
        检索最相关的 chunks
        
        Args:
            query: 查询文本
        
        Returns:
            排序的 chunks 列表（top-k）
        """
        self.logger.info(f"[Stage 5] 检索相关代码 | query_length={len(query)} | total_chunks={len(self.chunks)}")

        candidate_limit = max(self.top_k, self.vector_candidates, self.rerank_top_n)
        lexical_results = self._lexical_search(query, top_k=candidate_limit)
        if self.backend == "lexical" or self.vector_store is None:
            lexical_chunks = [self._build_lexical_chunk(item) for item in lexical_results]
            top_results = self._apply_rerank_if_needed(query, lexical_chunks)
            self.logger.info(f"[Stage 5] 词法检索完成 | 返回 {len(top_results)} 个相关 chunks")
            return top_results

        vector_results = self._vector_search(query)
        if self.backend == "vector":
            vector_chunks = [self._drop_internal_fields(item) for item in vector_results]
            top_results = self._apply_rerank_if_needed(query, vector_chunks)
            self.logger.info(f"[Stage 5] 向量检索完成 | 返回 {len(top_results)} 个相关 chunks")
            return top_results

        top_results = self._merge_results(lexical_results, vector_results)
        top_results = self._apply_rerank_if_needed(query, top_results)
        self.logger.info(f"[Stage 5] 混合检索完成 | 返回 {len(top_results)} 个相关 chunks")
        return top_results

    def get_backend_summary(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "lexical_backend": self.lexical_backend,
            "rerank_enabled": self.rerank_enabled,
            "rerank_top_n": self.rerank_top_n,
            "rerank_backend": self.reranker.backend if self.reranker else None,
            "collection_name": self.collection_name,
            **self.embedder.summary(),
            "top_k": self.top_k,
            "vector_candidates": self.vector_candidates,
        }

    def _build_collection_name(self) -> str:
        if self.workspace_root is None:
            return "workspace_default"
        workspace_hash = hashlib.sha1(str(self.workspace_root).encode("utf-8")).hexdigest()[:12]
        return f"workspace_{workspace_hash}"

    def _collection_manifest(self) -> str:
        pieces = []
        for chunk in self.chunks:
            text_hash = hashlib.sha1(chunk.get("text", "").encode("utf-8")).hexdigest()
            pieces.append(
                ":".join(
                    [
                        str(chunk.get("relative_path")),
                        str(chunk.get("start_line")),
                        str(chunk.get("end_line")),
                        str(chunk.get("chunk_kind", "")),
                        str(chunk.get("symbol", "")),
                        text_hash,
                    ]
                )
            )
        payload = "|".join(sorted(pieces))
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _vector_search(self, query: str) -> List[Dict[str, Any]]:
        if self.vector_store is None:
            return []

        query_vector = self.embedder.embed_text(query)
        embedding_dim = len(query_vector)
        manifest = self._collection_manifest()
        if self.vector_store.needs_reindex(
            collection_name=self.collection_name,
            manifest=manifest,
            dimension=embedding_dim,
        ):
            self._index_chunks(manifest)

        return self.vector_store.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            top_k=self.vector_candidates,
        )

    def _index_chunks(self, manifest: str) -> None:
        texts = [
            "\n".join(
                part
                for part in (chunk.get("summary", ""), chunk.get("relative_path", ""), chunk.get("text", ""))
                if part
            )
            for chunk in self.chunks
        ]
        vectors = self.embedder.embed_texts(texts)
        rows = []
        for chunk, vector in zip(self.chunks, vectors):
            rows.append(
                {
                    "chunk_id": self._chunk_id(chunk),
                    "relative_path": chunk.get("relative_path", "unknown"),
                    "language": chunk.get("language", "unknown"),
                    "start_line": chunk.get("start_line", 0),
                    "end_line": chunk.get("end_line", 0),
                    "summary": chunk.get("summary", ""),
                    "chunk_kind": chunk.get("chunk_kind", "chunk"),
                    "symbol": chunk.get("symbol", ""),
                    "text": chunk.get("text", ""),
                    "vector": vector,
                }
            )
        self.vector_store.replace_collection(
            collection_name=self.collection_name,
            manifest=manifest,
            dimension=self.embedder.dimension,
            rows=rows,
        )

    def _lexical_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if self.lexical_backend == "bm25":
            scores = self._bm25_search(query, top_k)
        else:
            scores = self._keyword_search(query, top_k)
        scores.sort(key=lambda item: item["lexical_score"], reverse=True)
        return scores[:top_k]

    def _bm25_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        query_terms = set(tokenize_text(query))
        scores = []

        for item in self.bm25_scorer.score(query, top_k=len(self.chunks)):
            chunk = item["chunk"]
            summary = chunk.get("summary", "").lower()
            symbol = chunk.get("symbol", "").lower()
            score = float(item["bm25_score"])
            if summary and any(term in summary for term in query_terms):
                score += 0.8
            if symbol and symbol in query_lower:
                score += 1.2
            elif symbol and any(term in symbol for term in query_terms):
                score += 0.6
            scores.append(
                {
                    "chunk_id": item["chunk_id"],
                    "chunk": chunk,
                    "lexical_score": score,
                    "lexical_backend": "bm25",
                    "matched_terms": item["matched_terms"],
                }
            )
        return scores

    def _keyword_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        scores = []
        query_words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[\u4e00-\u9fff]+", query.lower()))

        for chunk in self.chunks:
            text = chunk.get("text", "").lower()
            summary = chunk.get("summary", "").lower()
            symbol = chunk.get("symbol", "").lower()

            matching_words = len([word for word in query_words if word in text or word in summary])
            score = float(matching_words)
            if summary and any(word in summary for word in query_words):
                score += 2.0
            if symbol and symbol in query.lower():
                score += 4.0
            elif symbol and any(word in symbol for word in query_words):
                score += 2.5

            scores.append(
                {
                    "chunk_id": self._chunk_id(chunk),
                    "chunk": chunk,
                    "lexical_score": score,
                    "lexical_backend": "keyword",
                }
            )
        return scores

    def _merge_results(
        self,
        lexical_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        lexical_max = max((item["lexical_score"] for item in lexical_results), default=0.0)

        for item in lexical_results:
            chunk = dict(item["chunk"])
            chunk_id = item["chunk_id"]
            merged[chunk_id] = {
                **chunk,
                "chunk_id": chunk_id,
                "lexical_score": item["lexical_score"],
                "lexical_backend": item.get("lexical_backend", self.lexical_backend),
                "vector_score": 0.0,
                "retrieval_backend": "hybrid",
            }

        for item in vector_results:
            chunk_id = item["chunk_id"]
            base = merged.get(
                chunk_id,
                {
                    "relative_path": item["relative_path"],
                    "language": item["language"],
                    "start_line": item["start_line"],
                    "end_line": item["end_line"],
                    "summary": item.get("summary", ""),
                    "chunk_kind": item.get("chunk_kind", "chunk"),
                    "symbol": item.get("symbol", ""),
                    "text": item.get("text", ""),
                    "chunk_id": chunk_id,
                    "lexical_score": 0.0,
                    "lexical_backend": self.lexical_backend,
                    "retrieval_backend": "hybrid",
                },
            )
            base["vector_score"] = item["vector_score"]
            merged[chunk_id] = base

        results = []
        for chunk in merged.values():
            lexical_score = chunk.get("lexical_score", 0.0)
            lexical_norm = lexical_score / lexical_max if lexical_max > 0 else 0.0
            vector_score = max(chunk.get("vector_score", 0.0), 0.0)
            combined_score = (vector_score * 0.75) + (lexical_norm * 0.25)
            chunk["score"] = combined_score
            results.append(chunk)

        candidate_limit = max(self.top_k, self.vector_candidates, self.rerank_top_n)
        results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return [self._drop_internal_fields(item) for item in results[:candidate_limit]]

    def _build_lexical_chunk(self, item: Dict[str, Any]) -> Dict[str, Any]:
        chunk = dict(item["chunk"])
        chunk["lexical_score"] = item["lexical_score"]
        chunk["lexical_backend"] = item.get("lexical_backend", self.lexical_backend)
        chunk["score"] = item["lexical_score"]
        chunk["retrieval_backend"] = "lexical"
        return self._drop_internal_fields(chunk)

    def _apply_rerank_if_needed(
        self,
        query: str,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not self.reranker:
            return results[:self.top_k]
        reranked = self.reranker.rerank(query, results, top_n=self.rerank_top_n)
        return [self._drop_internal_fields(item) for item in reranked[:self.top_k]]

    @staticmethod
    def _chunk_id(chunk: Dict[str, Any]) -> str:
        return f"{chunk.get('relative_path', 'unknown')}:{chunk.get('start_line', 0)}:{chunk.get('end_line', 0)}"

    @staticmethod
    def _drop_internal_fields(chunk: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(chunk)
        result.pop("chunk_id", None)
        return result

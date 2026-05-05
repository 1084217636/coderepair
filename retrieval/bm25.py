"""
BM25 词法检索

为当前代码仓检索链提供一个更标准的 lexical scoring 实现。
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[\u4e00-\u9fff]+")


def tokenize_text(text: str) -> List[str]:
    """统一的轻量 tokenizer，兼顾代码符号、数字和中文连续片段。"""
    if not text:
        return []
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


@dataclass
class BM25Document:
    chunk_id: str
    chunk: Dict[str, Any]
    term_freq: Counter
    length: int


class BM25LexicalScorer:
    """为 chunk 列表提供 BM25 打分。"""

    def __init__(self, chunks: Iterable[Dict[str, Any]], *, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[BM25Document] = []
        self.doc_freq: Counter = Counter()
        self.avg_doc_len = 0.0

        total_length = 0
        for chunk in chunks:
            chunk_id = self._chunk_id(chunk)
            tokens = self._build_document_tokens(chunk)
            term_freq = Counter(tokens)
            doc_length = max(len(tokens), 1)
            self.documents.append(
                BM25Document(
                    chunk_id=chunk_id,
                    chunk=chunk,
                    term_freq=term_freq,
                    length=doc_length,
                )
            )
            total_length += doc_length
            self.doc_freq.update(term_freq.keys())

        self.avg_doc_len = (total_length / len(self.documents)) if self.documents else 0.0

    def score(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        query_terms = tokenize_text(query)
        if not self.documents:
            return []
        if not query_terms:
            return [
                {
                    "chunk_id": document.chunk_id,
                    "chunk": document.chunk,
                    "bm25_score": 0.0,
                    "matched_terms": 0,
                }
                for document in self.documents[:top_k]
            ]

        unique_terms = list(dict.fromkeys(query_terms))
        total_documents = len(self.documents)
        scored_results: List[Dict[str, Any]] = []

        for document in self.documents:
            score = 0.0
            matched_terms = 0
            for term in unique_terms:
                term_frequency = document.term_freq.get(term, 0)
                if term_frequency == 0:
                    continue
                matched_terms += 1
                document_frequency = self.doc_freq.get(term, 0)
                idf = math.log(((total_documents - document_frequency + 0.5) / (document_frequency + 0.5)) + 1.0)
                denominator = term_frequency + self.k1 * (
                    1 - self.b + self.b * (document.length / max(self.avg_doc_len, 1.0))
                )
                score += idf * ((term_frequency * (self.k1 + 1)) / max(denominator, 1e-9))

            scored_results.append(
                {
                    "chunk_id": document.chunk_id,
                    "chunk": document.chunk,
                    "bm25_score": float(score),
                    "matched_terms": matched_terms,
                }
            )

        scored_results.sort(key=lambda item: item["bm25_score"], reverse=True)
        return scored_results[:top_k]

    @staticmethod
    def _chunk_id(chunk: Dict[str, Any]) -> str:
        return f"{chunk.get('relative_path', 'unknown')}:{chunk.get('start_line', 0)}:{chunk.get('end_line', 0)}"

    @staticmethod
    def _build_document_tokens(chunk: Dict[str, Any]) -> List[str]:
        fields = [
            chunk.get("relative_path", ""),
            chunk.get("summary", ""),
            chunk.get("symbol", ""),
            chunk.get("text", ""),
        ]
        tokens: List[str] = []
        for index, field in enumerate(fields):
            field_tokens = tokenize_text(field)
            if not field_tokens:
                continue
            boost = 1
            if index == 1:  # summary
                boost = 2
            elif index == 2:  # symbol
                boost = 3
            tokens.extend(field_tokens * boost)
        return tokens

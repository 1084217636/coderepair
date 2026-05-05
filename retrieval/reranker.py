"""
轻量 rerank 模块

在初始召回之后，用证据特征做一层低成本重排。
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

from retrieval.bm25 import tokenize_text


ENGINEERING_HINTS = {
    "dockerfile",
    "go.mod",
    "gomod",
    "makefile",
    "readme",
    "module",
    "docker",
}

CODE_LANGUAGES = {"go", "python"}


class EvidenceReranker:
    """基于符号、摘要、路径和 chunk 类型做轻量 rerank。"""

    def __init__(self, *, backend: str = "heuristic"):
        self.backend = backend

    def rerank(self, query: str, results: Iterable[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
        ranked = list(results)
        if not ranked or top_n <= 0:
            return ranked

        query_lower = query.lower()
        query_terms = set(tokenize_text(query))
        if not query_terms:
            return ranked

        candidates = ranked[:top_n]
        remainder = ranked[top_n:]
        max_base = max((self._base_score(item) for item in candidates), default=0.0)

        reranked: List[Dict[str, Any]] = []
        for item in candidates:
            result = dict(item)
            base_score = self._base_score(result)
            base_norm = (base_score / max_base) if max_base > 0 else 0.0
            evidence_score, features = self._evidence_score(query_lower, query_terms, result)
            rerank_score = (base_norm * 0.7) + (evidence_score * 0.3)
            result["pre_rerank_score"] = base_score
            result["rerank_score"] = rerank_score
            result["rerank_backend"] = self.backend
            result["rerank_features"] = features
            result["score"] = rerank_score
            reranked.append(result)

        reranked.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return reranked + remainder

    @staticmethod
    def _base_score(item: Dict[str, Any]) -> float:
        for field in ("score", "vector_score", "lexical_score"):
            value = item.get(field)
            if isinstance(value, (int, float)):
                return float(value)
        return 0.0

    def _evidence_score(
        self,
        query_lower: str,
        query_terms: Set[str],
        item: Dict[str, Any],
    ) -> tuple[float, Dict[str, float]]:
        summary_terms = set(tokenize_text(item.get("summary", "")))
        symbol_terms = set(tokenize_text(item.get("symbol", "")))
        path_terms = set(tokenize_text(item.get("relative_path", "").replace(".", " ")))
        evidence_terms = summary_terms | symbol_terms

        symbol = (item.get("symbol") or "").lower()
        summary_coverage = self._coverage(query_terms, evidence_terms)
        path_coverage = self._coverage(query_terms, path_terms)
        symbol_signal = 0.0
        if symbol and symbol in query_lower:
            symbol_signal = 1.0
        elif query_terms & symbol_terms:
            symbol_signal = 0.6

        kind_preference = self._kind_preference(query_terms, item)
        evidence_score = (
            (summary_coverage * 0.45)
            + (path_coverage * 0.15)
            + (symbol_signal * 0.25)
            + (kind_preference * 0.15)
        )
        return evidence_score, {
            "summary_coverage": round(summary_coverage, 4),
            "path_coverage": round(path_coverage, 4),
            "symbol_signal": round(symbol_signal, 4),
            "kind_preference": round(kind_preference, 4),
        }

    def _kind_preference(self, query_terms: Set[str], item: Dict[str, Any]) -> float:
        language = item.get("language", "")
        chunk_kind = item.get("chunk_kind", "")
        is_engineering_query = bool(query_terms & ENGINEERING_HINTS)
        is_code_chunk = language in CODE_LANGUAGES

        if is_engineering_query:
            return 1.0 if not is_code_chunk else 0.25

        if not is_code_chunk:
            return 0.3

        if chunk_kind in {"function", "method"}:
            return 1.0
        if chunk_kind in {"type", "file_header"}:
            return 0.7
        return 0.5

    @staticmethod
    def _coverage(query_terms: Set[str], evidence_terms: Set[str]) -> float:
        if not query_terms or not evidence_terms:
            return 0.0
        return len(query_terms & evidence_terms) / len(query_terms)

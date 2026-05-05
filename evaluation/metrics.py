"""
运行评估与批量评估
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class BenchmarkCase:
    name: str
    workspace_root: str
    query: str
    description: str = ""
    category: str = "general"
    mode: str = "single"
    expected_files: Optional[List[str]] = None
    expected_keywords: Optional[List[str]] = None
    focus_file: Optional[str] = None
    expect_validation: bool = False


class RunMetricsEvaluator:
    """按单次执行结果生成评估指标。"""

    @staticmethod
    def _tokenize_query(query: str) -> List[str]:
        return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[\u4e00-\u9fff]{2,}", query.lower())

    def evaluate_run(
        self,
        user_query: str,
        retrieval_summary: Dict[str, Any],
        extracted_code_blocks: List[str],
        apply_output: Optional[Dict[str, Any]],
        validation_output: Optional[Dict[str, Any]],
        analysis_output: Dict[str, Any],
        execution_mode: str,
        tool_calls: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        query_terms = self._tokenize_query(user_query)
        retrieved_results = retrieval_summary.get("results", [])

        matched_terms = 0
        if query_terms and retrieved_results:
            retrieved_text = "\n".join(
                f"{item.get('relative_path', '')}\n{item.get('summary', '')}\n{item.get('text', '')[:400]}"
                for item in retrieved_results
            ).lower()
            matched_terms = sum(1 for term in set(query_terms) if term in retrieved_text)

        hit_rate = matched_terms / len(set(query_terms)) if query_terms else 0.0
        precheck_summary = analysis_output.get("go_precheck_summary", {})
        precheck_total = sum(value for value in precheck_summary.values() if isinstance(value, int))
        code_chunks = [
            item for item in retrieved_results
            if item.get("language") in {"go", "python"}
        ]
        engineering_chunks = [
            item for item in retrieved_results
            if item.get("language") not in {"go", "python"}
        ]
        retrieval_scores = [
            item.get("score", item.get("rerank_score", item.get("vector_score", item.get("lexical_score", 0.0))))
            for item in retrieved_results
            if isinstance(
                item.get("score", item.get("rerank_score", item.get("vector_score", item.get("lexical_score")))),
                (int, float),
            )
        ]
        reranked_chunks = sum(1 for item in retrieved_results if "rerank_score" in item)
        primary_score = retrieval_scores[0] if retrieval_scores else 0.0
        avg_retrieval_score = (
            sum(retrieval_scores) / len(retrieval_scores)
            if retrieval_scores
            else 0.0
        )
        code_chunk_ratio = (len(code_chunks) / len(retrieved_results)) if retrieved_results else 0.0

        apply_status = apply_output.get("status") if apply_output else "analysis_only"
        validation_passed = bool(validation_output and validation_output.get("success"))
        repair_success = apply_status == "validated" or (
            apply_status == "analysis_only" and validation_passed
        )
        tool_call_items = (tool_calls or {}).get("calls", [])
        failed_tool_calls = [
            item for item in tool_call_items
            if item.get("status") in {"error", "failed"}
        ]

        return {
            "metrics_version": "v2",
            "execution_mode": execution_mode,
            "rag_backend": (retrieval_summary.get("rag") or {}).get("backend"),
            "lexical_backend": (retrieval_summary.get("rag") or {}).get("lexical_backend"),
            "embedding_provider": (retrieval_summary.get("rag") or {}).get("provider"),
            "rerank_enabled": bool((retrieval_summary.get("rag") or {}).get("rerank_enabled")),
            "rerank_backend": (retrieval_summary.get("rag") or {}).get("rerank_backend"),
            "retrieved_chunks": retrieval_summary.get("retrieved_chunks", 0),
            "retrieved_files": len({item.get("relative_path") for item in retrieved_results}),
            "retrieved_code_chunks": len(code_chunks),
            "retrieved_engineering_chunks": len(engineering_chunks),
            "retrieved_code_ratio": round(code_chunk_ratio, 4),
            "retrieval_hit_rate": round(hit_rate, 4),
            "primary_score": round(primary_score, 4),
            "avg_retrieval_score": round(avg_retrieval_score, 4),
            "reranked_chunks": reranked_chunks,
            "code_block_count": len(extracted_code_blocks),
            "precheck_issue_total": precheck_total,
            "call_relations_count": analysis_output.get("call_relations_count", 0),
            "dependency_span": analysis_output.get("dependency_span"),
            "validation_passed": validation_passed,
            "repair_status": apply_status,
            "repair_success": repair_success,
            "tool_call_count": len(tool_call_items),
            "failed_tool_call_count": len(failed_tool_calls),
        }

    @staticmethod
    def aggregate_suite(results: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        results = list(results)
        if not results:
            return {
                "cases": 0,
                "avg_retrieval_hit_rate": 0.0,
                "avg_primary_score": 0.0,
                "avg_retrieval_score": 0.0,
                "avg_retrieved_code_ratio": 0.0,
                "rerank_usage_rate": 0.0,
                "validation_pass_rate": 0.0,
                "repair_success_rate": 0.0,
            }

        total = len(results)
        avg_hit_rate = sum(item.get("retrieval_hit_rate", 0.0) for item in results) / total
        avg_primary_score = sum(item.get("primary_score", 0.0) for item in results) / total
        avg_retrieval_score = sum(item.get("avg_retrieval_score", 0.0) for item in results) / total
        avg_retrieved_code_ratio = sum(item.get("retrieved_code_ratio", 0.0) for item in results) / total
        rerank_usage_rate = sum(1 for item in results if item.get("rerank_enabled")) / total
        validation_pass_rate = sum(1 for item in results if item.get("validation_passed")) / total
        repair_success_rate = sum(1 for item in results if item.get("repair_success")) / total
        return {
            "cases": total,
            "avg_retrieval_hit_rate": round(avg_hit_rate, 4),
            "avg_primary_score": round(avg_primary_score, 4),
            "avg_retrieval_score": round(avg_retrieval_score, 4),
            "avg_retrieved_code_ratio": round(avg_retrieved_code_ratio, 4),
            "rerank_usage_rate": round(rerank_usage_rate, 4),
            "validation_pass_rate": round(validation_pass_rate, 4),
            "repair_success_rate": round(repair_success_rate, 4),
        }

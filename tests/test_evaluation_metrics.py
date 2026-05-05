from evaluation.metrics import RunMetricsEvaluator


def test_run_metrics_evaluator_computes_single_run_metrics():
    evaluator = RunMetricsEvaluator()
    metrics = evaluator.evaluate_run(
        user_query="分析 user service 的启动流程",
        retrieval_summary={
            "rag": {
                "backend": "hybrid",
                "provider": "ollama",
                "lexical_backend": "bm25",
                "rerank_enabled": True,
                "rerank_backend": "heuristic",
            },
            "retrieved_chunks": 2,
            "results": [
                {
                    "relative_path": "internal/service/user.go",
                    "language": "go",
                    "summary": "user service start",
                    "text": "func StartUserService() {}",
                    "score": 0.91,
                    "rerank_score": 0.91,
                },
                {
                    "relative_path": "cmd/server/main.go",
                    "language": "go",
                    "summary": "server main entry",
                    "text": "func main() {}",
                    "score": 0.76,
                },
            ],
        },
        extracted_code_blocks=["package main\nfunc main() {}"],
        apply_output={"status": "validated"},
        validation_output={"success": True},
        analysis_output={
            "go_precheck_summary": {"imports": 1, "unused": 0},
            "call_relations_count": 4,
            "dependency_span": {"external_imports": 1},
        },
        execution_mode="single",
    )

    assert metrics["rag_backend"] == "hybrid"
    assert metrics["lexical_backend"] == "bm25"
    assert metrics["embedding_provider"] == "ollama"
    assert metrics["rerank_enabled"] is True
    assert metrics["rerank_backend"] == "heuristic"
    assert metrics["retrieved_chunks"] == 2
    assert metrics["retrieved_files"] == 2
    assert metrics["retrieved_code_chunks"] == 2
    assert metrics["retrieved_engineering_chunks"] == 0
    assert metrics["primary_score"] == 0.91
    assert metrics["avg_retrieval_score"] == 0.835
    assert metrics["reranked_chunks"] == 1
    assert metrics["code_block_count"] == 1
    assert metrics["precheck_issue_total"] == 1
    assert metrics["call_relations_count"] == 4
    assert metrics["validation_passed"] is True
    assert metrics["repair_success"] is True


def test_run_metrics_evaluator_can_aggregate_suite():
    summary = RunMetricsEvaluator.aggregate_suite(
        [
            {
                "retrieval_hit_rate": 0.8,
                "primary_score": 0.7,
                "avg_retrieval_score": 0.6,
                "retrieved_code_ratio": 1.0,
                "rerank_enabled": True,
                "validation_passed": True,
                "repair_success": True,
            },
            {
                "retrieval_hit_rate": 0.4,
                "primary_score": 0.2,
                "avg_retrieval_score": 0.3,
                "retrieved_code_ratio": 0.5,
                "rerank_enabled": False,
                "validation_passed": False,
                "repair_success": False,
            },
        ]
    )

    assert summary == {
        "cases": 2,
        "avg_retrieval_hit_rate": 0.6,
        "avg_primary_score": 0.45,
        "avg_retrieval_score": 0.45,
        "avg_retrieved_code_ratio": 0.75,
        "rerank_usage_rate": 0.5,
        "validation_pass_rate": 0.5,
        "repair_success_rate": 0.5,
    }

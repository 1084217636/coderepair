from deerflow.code_change.evaluation import EvaluationCase, _patch, run_evaluation


def test_evaluation_reports_success_failure_and_safety_metrics(tmp_path):
    cases = [
        EvaluationCase("success", "success", _patch(0, 1), 1),
        EvaluationCase("unsafe", "unsafe_path", _patch(0, 1, "../escape.py"), 1),
        EvaluationCase("test-fail", "test_failure", _patch(0, 1), 99),
    ]

    result = run_evaluation(tmp_path / "report", cases)

    assert result["metrics"]["task_count"] == 3
    assert result["metrics"]["patch_apply_rate"] == 0.6667
    assert result["metrics"]["task_success_rate"] == 0.3333
    assert result["metrics"]["unsafe_patch_block_rate"] == 1.0
    assert result["metrics"]["human_acceptance_rate"] is None
    assert (tmp_path / "report" / "evaluation.json").exists()
    assert (tmp_path / "report" / "evaluation.md").exists()

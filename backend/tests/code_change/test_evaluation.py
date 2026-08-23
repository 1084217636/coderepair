from deerflow.code_change.evaluation import EvaluationCase, _patch, fixed_cases, run_evaluation


def test_fixed_release_gate_has_exactly_twenty_cases():
    cases = fixed_cases()

    assert len(cases) == 20
    assert {case.kind for case in cases} == {"success", "invalid_context", "unsafe_path", "test_failure"}


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

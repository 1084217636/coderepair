from deerflow.code_change.agent_evaluation import agent_cases


def test_agent_evaluation_has_twelve_small_verifiable_tasks() -> None:
    cases = agent_cases()

    assert len(cases) == 12
    assert len({case.case_id for case in cases}) == 12
    assert all("app.py" in case.files and "test_app.py" in case.files for case in cases)
    assert any(case.expected_files == ("app.py", "test_app.py") for case in cases)

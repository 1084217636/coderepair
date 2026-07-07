from deerflow.code_change.test_runner import run_tests


def test_run_tests_blocks_disallowed_shell_operator(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = run_tests(str(repo), "python3 -c 'print(1)' && rm -rf /", tmp_path / "artifacts")

    assert result.exit_code == 126
    assert "blocked by sandbox policy" in (tmp_path / "artifacts" / "test.log").read_text(encoding="utf-8")
    assert result.policy_path


def test_run_tests_uses_shell_false_and_allows_python(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = run_tests(str(repo), "python3 -c 'print(\"ok\")'", tmp_path / "artifacts")

    assert result.exit_code == 0
    assert (tmp_path / "artifacts" / "test.log").read_text(encoding="utf-8").strip() == "ok"
    assert result.timed_out is False
    assert result.log_truncated is False

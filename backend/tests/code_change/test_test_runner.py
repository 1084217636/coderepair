import sys

import pytest

from deerflow.code_change.sandbox_policy import SandboxPolicy, SandboxPolicyViolation, build_command
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


def test_build_command_allows_versioned_virtualenv_python():
    policy = SandboxPolicy(allowed_executables=["python3", "pytest"])

    args = build_command("/tmp/project/.venv/bin/python3.12 -m pytest -q", policy)

    assert args == ["/tmp/project/.venv/bin/python3.12", "-m", "pytest", "-q"]


def test_run_tests_executes_versioned_virtualenv_python(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    versioned_python = tmp_path / "python3.12"
    versioned_python.symlink_to(sys.executable)

    result = run_tests(str(repo), f"{versioned_python} -c \"print('versioned ok')\"", tmp_path / "artifacts")

    assert result.exit_code == 0
    assert (tmp_path / "artifacts" / "test.log").read_text(encoding="utf-8").strip() == "versioned ok"


def test_build_command_rejects_python_prefix_impersonation():
    policy = SandboxPolicy(allowed_executables=["python3"])

    with pytest.raises(SandboxPolicyViolation, match="executable is not allowed"):
        build_command("python3.12evil -m pytest", policy)

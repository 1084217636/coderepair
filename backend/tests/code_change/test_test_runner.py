import os
import shlex
import sys
import time

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


def test_run_tests_does_not_inherit_gateway_secrets(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("DEER_FLOW_INTERNAL_AUTH_TOKEN", "must-not-leak-either")
    command = f"{sys.executable} -c \"import os; assert os.getenv('OPENAI_API_KEY') is None; assert os.getenv('DEER_FLOW_INTERNAL_AUTH_TOKEN') is None\""

    result = run_tests(str(repo), command, tmp_path / "artifacts")

    assert result.exit_code == 0
    assert os.environ["OPENAI_API_KEY"] == "must-not-leak"
    assert (tmp_path / "artifacts" / "test-home").is_dir()


@pytest.mark.skipif(os.name != "posix", reason="POSIX process groups are required for this assertion")
def test_run_tests_timeout_kills_spawned_process_group(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    marker = tmp_path / "orphan-marker"
    child = f"import time, pathlib; time.sleep(0.4); pathlib.Path({str(marker)!r}).write_text('orphan')"
    parent = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(5)"

    result = run_tests(str(repo), shlex.join([sys.executable, "-c", parent]), tmp_path / "artifacts", timeout=0.1)
    time.sleep(0.6)

    assert result.exit_code == 124
    assert result.timed_out is True
    assert not marker.exists()

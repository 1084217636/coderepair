from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

from deerflow.code_change.models import TestResult
from deerflow.code_change.sandbox_policy import SandboxPolicy, SandboxPolicyViolation, build_command, default_policy, write_policy

_INHERITED_TEST_ENV = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "VIRTUAL_ENV",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "GOCACHE",
    "GOMODCACHE",
    "GOPATH",
)


def run_tests(repo_path: str, command: str, artifact_dir: str | Path, timeout: int = 120, policy: SandboxPolicy | None = None) -> TestResult:
    policy = policy or default_policy()
    if timeout > 0:
        policy.timeout_seconds = timeout
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    log_path = artifacts / "test.log"
    policy_path = write_policy(policy, artifacts)
    test_env = build_test_environment(artifacts)
    start = time.monotonic()
    try:
        args = build_command(command, policy)
    except SandboxPolicyViolation as exc:
        duration = time.monotonic() - start
        log_path.write_text(f"blocked by sandbox policy: {exc}\n", encoding="utf-8")
        return TestResult(
            command=command,
            exit_code=126,
            duration_seconds=round(duration, 3),
            log_path=str(log_path),
            policy_path=str(policy_path),
        )

    timed_out = False
    try:
        proc = subprocess.Popen(
            args,
            cwd=repo_path,
            shell=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=test_env,
            start_new_session=os.name == "posix",
        )
        output, _ = proc.communicate(timeout=policy.timeout_seconds)
        exit_code = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        _kill_process_tree(proc)
        output, _ = proc.communicate()
        output = output or exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        output += f"\ncommand timed out after {policy.timeout_seconds}s\n"
        exit_code = 124
    except OSError as exc:
        output = f"failed to start test command: {exc}\n"
        exit_code = 127
    duration = time.monotonic() - start
    output_bytes = output.encode("utf-8")
    truncated = len(output_bytes) > policy.max_log_bytes
    if truncated:
        output_bytes = output_bytes[: policy.max_log_bytes] + b"\n...[truncated by sandbox policy]\n"
        output = output_bytes.decode("utf-8", errors="replace")
    log_path.write_text(output, encoding="utf-8")
    return TestResult(
        command=command,
        exit_code=exit_code,
        duration_seconds=round(duration, 3),
        log_path=str(log_path),
        timed_out=timed_out,
        log_truncated=truncated,
        policy_path=str(policy_path),
    )


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
    process.kill()


def build_test_environment(artifact_dir: str | Path) -> dict[str, str]:
    artifacts = Path(artifact_dir)
    home = artifacts / "test-home"
    temp = artifacts / "test-tmp"
    home.mkdir(parents=True, exist_ok=True)
    temp.mkdir(parents=True, exist_ok=True)
    env = {name: os.environ[name] for name in _INHERITED_TEST_ENV if name in os.environ}
    env.update(
        {
            "HOME": str(home),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "TMPDIR": str(temp),
            "TMP": str(temp),
            "TEMP": str(temp),
            "NO_COLOR": "1",
        }
    )
    return env

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from deerflow.code_change.models import TestResult


def run_tests(repo_path: str, command: str, artifact_dir: str | Path, timeout: int = 120) -> TestResult:
    start = time.monotonic()
    proc = subprocess.run(
        command,
        cwd=repo_path,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    duration = time.monotonic() - start
    log_path = Path(artifact_dir) / "test.log"
    log_path.write_text(proc.stdout, encoding="utf-8")
    return TestResult(command=command, exit_code=proc.returncode, duration_seconds=round(duration, 3), log_path=str(log_path))

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def committed_repo(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    def create(files: dict[str, str]) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Code Change Tests"], cwd=repo, check=True)
        for relative_path, content in files.items():
            path = repo / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo, check=True)
        return repo

    return create

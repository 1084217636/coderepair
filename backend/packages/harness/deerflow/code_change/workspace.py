from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path


IGNORED_DIRS = {
    ".git",
    ".deer-flow",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "target",
}


@dataclass(slots=True)
class Workspace:
    source_repo_path: str
    workspace_path: str
    sandbox_kind: str = "local-copy"


def prepare_workspace(repo_path: str, artifact_dir: str | Path) -> Workspace:
    source = Path(repo_path).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        raise ValueError(f"repo_path does not exist or is not a directory: {repo_path}")

    workspace = Path(artifact_dir) / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(source, workspace, ignore=_ignore_names)
    return Workspace(
        source_repo_path=str(source),
        workspace_path=str(workspace),
    )


def _ignore_names(_: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_DIRS}

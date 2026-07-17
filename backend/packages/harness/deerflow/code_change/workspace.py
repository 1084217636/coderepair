from __future__ import annotations

import json
import shutil
import time
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
    manifest_path: str = ""
    file_count: int = 0
    total_bytes: int = 0


def prepare_workspace(repo_path: str, artifact_dir: str | Path) -> Workspace:
    source = Path(repo_path).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        raise ValueError(f"repo_path does not exist or is not a directory: {repo_path}")

    workspace = Path(artifact_dir) / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    start = time.monotonic()
    shutil.copytree(source, workspace, ignore=_ignore_names)
    file_count, total_bytes = _workspace_stats(workspace)
    manifest_path = Path(artifact_dir) / "workspace_manifest.json"
    manifest = {
        "sandbox_kind": "local-copy",
        "source_repo_path": str(source),
        "workspace_path": str(workspace),
        "ignored_dirs": sorted(IGNORED_DIRS),
        "file_count": file_count,
        "total_bytes": total_bytes,
        "duration_ms": round((time.monotonic() - start) * 1000),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return Workspace(
        source_repo_path=str(source),
        workspace_path=str(workspace),
        manifest_path=str(manifest_path),
        file_count=file_count,
        total_bytes=total_bytes,
    )


def _ignore_names(_: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORED_DIRS}


def _workspace_stats(path: Path) -> tuple[int, int]:
    file_count = 0
    total_bytes = 0
    for item in path.rglob("*"):
        if item.is_file():
            file_count += 1
            total_bytes += item.stat().st_size
    return file_count, total_bytes

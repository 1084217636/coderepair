from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

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
    source_commit: str = ""
    sandbox_kind: str = "local-copy"
    manifest_path: str = ""
    file_count: int = 0
    total_bytes: int = 0


def resolve_source_commit(repo_path: str | Path) -> str:
    source = Path(repo_path).expanduser().resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=source,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    commit = result.stdout.strip()
    if result.returncode != 0 or len(commit) != 40:
        detail = commit or "repository has no committed HEAD"
        raise ValueError(f"repo_path must be a Git repository with a committed HEAD: {detail}")
    return commit


def prepare_workspace(repo_path: str, artifact_dir: str | Path, *, source_commit: str = "") -> Workspace:
    source = Path(repo_path).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        raise ValueError(f"repo_path does not exist or is not a directory: {repo_path}")

    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)
    workspace = artifact_path / "workspace"
    staging = artifact_path / f".workspace-{uuid4().hex}.tmp"
    archive = artifact_path / f".workspace-{uuid4().hex}.tar"
    start = time.monotonic()
    try:
        if source_commit:
            _export_commit(source, source_commit, staging, archive)
        else:
            shutil.copytree(source, staging, ignore=_ignore_names)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        archive.unlink(missing_ok=True)
    if workspace.exists():
        shutil.rmtree(workspace)
    staging.replace(workspace)
    file_count, total_bytes = _workspace_stats(workspace)
    manifest_path = artifact_path / "workspace_manifest.json"
    manifest = {
        "sandbox_kind": "local-copy",
        "source_repo_path": str(source),
        "source_commit": source_commit,
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
        source_commit=source_commit,
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


def _export_commit(source: Path, source_commit: str, staging: Path, archive: Path) -> None:
    result = subprocess.run(
        ["git", "archive", "--format=tar", "--output", str(archive), source_commit],
        cwd=source,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"cannot export source commit {source_commit}: {result.stdout.strip()}")
    staging.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, mode="r") as bundle:
        bundle.extractall(staging, filter="data")

import json
import subprocess
from pathlib import Path

import pytest

from deerflow.code_change import workspace as workspace_module
from deerflow.code_change.workspace import prepare_workspace


def test_prepare_workspace_copies_repo_without_polluting_source(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "app.py").write_text("value = 'source'\n", encoding="utf-8")

    workspace = prepare_workspace(str(repo), tmp_path / "artifacts")
    workspace_file = tmp_path / "artifacts" / "workspace" / "app.py"

    assert workspace.sandbox_kind == "local-copy"
    assert workspace.manifest_path
    assert workspace.file_count == 1
    assert workspace.total_bytes > 0
    assert workspace_file.exists()
    assert not (tmp_path / "artifacts" / "workspace" / ".git").exists()
    manifest = json.loads((tmp_path / "artifacts" / "workspace_manifest.json").read_text(encoding="utf-8"))
    assert manifest["file_count"] == 1
    assert ".git" in manifest["ignored_dirs"]

    workspace_file.write_text("value = 'changed'\n", encoding="utf-8")

    assert (repo / "app.py").read_text(encoding="utf-8") == "value = 'source'\n"


def test_prepare_workspace_keeps_previous_copy_when_refresh_fails(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("version = 1\n", encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    prepare_workspace(str(repo), artifacts)
    (repo / "app.py").write_text("version = 2\n", encoding="utf-8")

    def fail_copy(*args, **kwargs):
        raise OSError("copy interrupted")

    monkeypatch.setattr(workspace_module.shutil, "copytree", fail_copy)

    with pytest.raises(OSError, match="copy interrupted"):
        prepare_workspace(str(repo), artifacts)

    assert (artifacts / "workspace" / "app.py").read_text(encoding="utf-8") == "version = 1\n"


def test_prepare_workspace_uses_fixed_commit_not_dirty_worktree(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "value = 'committed'\n"})
    source_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    (repo / "app.py").write_text("value = 'dirty'\n", encoding="utf-8")

    workspace = prepare_workspace(str(repo), tmp_path / "artifacts", source_commit=source_commit)

    assert workspace.source_commit == source_commit
    assert (Path(workspace.workspace_path) / "app.py").read_text(encoding="utf-8") == "value = 'committed'\n"

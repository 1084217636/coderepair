import json

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

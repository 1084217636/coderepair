import pytest

from deerflow.code_change.store import CodeChangeStore


def test_store_creates_project(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    store = CodeChangeStore(tmp_path / "state")

    project = store.create_project("demo", str(repo), "python -c 'print(1)'")

    assert project.project_id == "demo"
    assert store.get_project("demo").repo_path == str(repo.resolve())
    assert len(store.list_projects()) == 1
    assert (tmp_path / "state" / "projects" / "demo" / "timeline.jsonl").exists()


def test_store_isolates_projects_by_owner(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    state = tmp_path / "state"
    alice = CodeChangeStore(state, owner_id="alice", allowed_repo_roots=[tmp_path])
    bob = CodeChangeStore(state, owner_id="bob", allowed_repo_roots=[tmp_path])

    alice.create_project("demo", str(repo), "python3 -V")
    bob.create_project("demo", str(repo), "python3 -V")

    assert alice.get_project("demo").owner_id == "alice"
    assert bob.get_project("demo").owner_id == "bob"
    assert alice.project_dir("demo") != bob.project_dir("demo")


def test_store_rejects_repo_outside_allowed_roots(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    store = CodeChangeStore(tmp_path / "state", allowed_repo_roots=[allowed])

    with pytest.raises(ValueError, match="allowed repository roots"):
        store.create_project("demo", str(outside), "python3 -V")

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

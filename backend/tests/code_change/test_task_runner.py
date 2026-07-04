import sys

from deerflow.code_change.cli import run_task
from deerflow.code_change.models import TaskStatus
from deerflow.code_change.store import CodeChangeStore


def test_task_runner_writes_report_and_test_log(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def health():\n    return 'ok'\n", encoding="utf-8")
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f"{sys.executable} -c \"print('tests ok')\"")

    task = run_task(store, "demo", "check health function")

    artifact_dir = tmp_path / "state" / "projects" / "demo" / "tasks" / task.task_id
    assert task.status == TaskStatus.REVIEWING
    assert (artifact_dir / "task_report.md").exists()
    assert (artifact_dir / "test.log").read_text(encoding="utf-8").strip() == "tests ok"
    assert (artifact_dir / "audit.json").exists()

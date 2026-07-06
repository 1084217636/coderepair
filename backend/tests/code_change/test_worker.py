import subprocess
import sys

from deerflow.code_change.models import TaskStatus
from deerflow.code_change.store import CodeChangeStore
from deerflow.code_change.worker import create_task, run_next_task


def test_worker_runs_queued_patch_task(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "app.py").write_text("def health():\n    return 'bad'\n", encoding="utf-8")

    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""
    store = CodeChangeStore(tmp_path / "state")
    command = f"{sys.executable} -c \"import app; assert app.health() == 'ok'; print('tests ok')\""
    store.create_project("demo", str(repo), command)

    queued = create_task(store, "demo", "fix health function", patch_text=patch, enqueue=True)

    assert queued.status == TaskStatus.QUEUED
    assert (tmp_path / "state" / "task_queue.jsonl").exists()

    finished = run_next_task(store)

    assert finished is not None
    assert finished.task_id == queued.task_id
    assert finished.status == TaskStatus.PR_CREATED
    assert finished.patch_result is not None
    assert finished.patch_result.changed_files == ["app.py"]
    assert (tmp_path / "state" / "projects" / "demo" / "tasks" / queued.task_id / "pr_body.md").exists()


def test_worker_noops_when_queue_is_empty(tmp_path):
    store = CodeChangeStore(tmp_path / "state")

    assert run_next_task(store) is None

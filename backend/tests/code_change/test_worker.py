import subprocess
import sys
from pathlib import Path

from deerflow.code_change.models import TaskStatus
from deerflow.code_change.store import CodeChangeStore
from deerflow.code_change.worker import create_task, retry_task, run_next_task


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
    assert finished.attempt_count == 1
    assert finished.started_at
    assert finished.finished_at
    assert finished.sandbox_kind == "local-copy"
    assert finished.workspace_path
    assert finished.patch_result is not None
    assert finished.patch_result.changed_files == ["app.py"]
    assert (repo / "app.py").read_text(encoding="utf-8") == "def health():\n    return 'bad'\n"
    assert "return 'ok'" in (Path(finished.workspace_path) / "app.py").read_text(encoding="utf-8")
    assert (tmp_path / "state" / "projects" / "demo" / "tasks" / queued.task_id / "pr_body.md").exists()

    metrics = store.task_metrics("demo")
    assert metrics["status_counts"]["PR_CREATED"] == 1
    assert metrics["queue_depth"] == 0
    assert metrics["attempts_total"] == 1


def test_worker_noops_when_queue_is_empty(tmp_path):
    store = CodeChangeStore(tmp_path / "state")

    assert run_next_task(store) is None


def test_retry_failed_task_requeues_until_attempts_exhausted(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "app.py").write_text("def health():\n    return 'bad'\n", encoding="utf-8")

    bad_patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -10,2 +10,2 @@
 def missing():
-    return 'bad'
+    return 'ok'
"""
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f"{sys.executable} -c \"print('tests ok')\"")
    queued = create_task(store, "demo", "apply impossible patch", patch_text=bad_patch, enqueue=True)

    failed = run_next_task(store)

    assert failed is not None
    assert failed.status == TaskStatus.FAILED
    assert failed.attempt_count == 1
    assert store.task_metrics("demo")["retryable_failed_count"] == 1

    retried = retry_task(store, "demo", queued.task_id)

    assert retried.status == TaskStatus.QUEUED
    assert retried.attempt_count == 1
    assert retried.last_error

    failed_again = run_next_task(store)

    assert failed_again is not None
    assert failed_again.status == TaskStatus.FAILED
    assert failed_again.attempt_count == 2
    assert store.task_metrics("demo")["exhausted_failed_count"] == 1

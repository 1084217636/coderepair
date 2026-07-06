import sys
import subprocess
from pathlib import Path

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


def test_task_runner_applies_patch_and_writes_pr_body(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "app.py").write_text("def health():\n    return 'bad'\n", encoding="utf-8")
    patch = tmp_path / "fix.patch"
    patch.write_text(
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
""",
        encoding="utf-8",
    )
    command = f"{sys.executable} -c \"import app; assert app.health() == 'ok'; print('tests ok')\""
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), command)

    task = run_task(store, "demo", "fix health function", patch_file=str(patch))

    artifact_dir = tmp_path / "state" / "projects" / "demo" / "tasks" / task.task_id
    assert task.status == TaskStatus.PR_CREATED
    assert task.sandbox_kind == "local-copy"
    assert task.workspace_path
    assert task.patch_result is not None
    assert task.patch_result.applied is True
    assert (repo / "app.py").read_text(encoding="utf-8") == "def health():\n    return 'bad'\n"
    assert "return 'ok'" in (Path(task.workspace_path) / "app.py").read_text(encoding="utf-8")
    assert (artifact_dir / "patch.diff").exists()
    assert (artifact_dir / "pr_body.md").exists()
    assert "Result: `PASS`" in (artifact_dir / "pr_body.md").read_text(encoding="utf-8")
    assert (artifact_dir / "audit.json").exists()

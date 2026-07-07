import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers import code_change
from deerflow.code_change.store import CodeChangeStore


def test_code_change_router_runs_patch_task(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "app.py").write_text("def health():\n    return 'bad'\n", encoding="utf-8")

    store = CodeChangeStore(tmp_path / "state")
    app = FastAPI()
    app.dependency_overrides[code_change.get_code_change_store] = lambda: store
    app.include_router(code_change.router)
    client = TestClient(app)

    create_resp = client.post(
        "/api/code-change/projects",
        json={
            "name": "demo",
            "repo_path": str(repo),
            "test_command": "python3 -c \"import app; assert app.health() == 'ok'; print('tests ok')\"",
        },
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["project_id"] == "demo"

    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""
    task_resp = client.post(
        "/api/code-change/projects/demo/tasks",
        json={"requirement": "fix health function", "patch_text": patch},
    )
    assert task_resp.status_code == 200
    task = task_resp.json()
    assert task["status"] == "QUEUED"

    worker_resp = client.post("/api/code-change/worker/run-once")
    assert worker_resp.status_code == 200
    task = worker_resp.json()
    assert task["status"] == "PR_CREATED"
    assert task["attempt_count"] == 1
    assert task["sandbox_kind"] == "local-copy"
    assert task["workspace_path"]
    assert task["workspace_manifest_path"]
    assert task["pr_handoff_path"]
    assert task["pr_create_script_path"]
    assert task["patch_result"]["changed_files"] == ["app.py"]
    assert (repo / "app.py").read_text(encoding="utf-8") == "def health():\n    return 'bad'\n"
    assert "return 'ok'" in (Path(task["workspace_path"]) / "app.py").read_text(encoding="utf-8")

    task_id = task["task_id"]
    detail_resp = client.get(f"/api/code-change/projects/demo/tasks/{task_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "PR_CREATED"

    report_resp = client.get(f"/api/code-change/projects/demo/tasks/{task_id}/report")
    assert report_resp.status_code == 200
    assert "Code Change Task Report" in report_resp.text

    pr_resp = client.get(f"/api/code-change/projects/demo/tasks/{task_id}/pr-body")
    assert pr_resp.status_code == 200
    assert "Result: `PASS`" in pr_resp.text

    timeline_resp = client.get("/api/code-change/projects/demo/timeline")
    assert timeline_resp.status_code == 200
    assert len(timeline_resp.json()["events"]) >= 2

    metrics_resp = client.get("/api/code-change/metrics?project_id=demo")
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["status_counts"]["PR_CREATED"] == 1


def test_code_change_router_retries_failed_task(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "app.py").write_text("def health():\n    return 'bad'\n", encoding="utf-8")

    store = CodeChangeStore(tmp_path / "state")
    app = FastAPI()
    app.dependency_overrides[code_change.get_code_change_store] = lambda: store
    app.include_router(code_change.router)
    client = TestClient(app)

    assert client.post(
        "/api/code-change/projects",
        json={
            "name": "demo",
            "repo_path": str(repo),
            "test_command": "python3 -c \"print('tests ok')\"",
        },
    ).status_code == 200

    bad_patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -10,2 +10,2 @@
 def missing():
-    return 'bad'
+    return 'ok'
"""
    task_resp = client.post(
        "/api/code-change/projects/demo/tasks",
        json={"requirement": "apply impossible patch", "patch_text": bad_patch},
    )
    assert task_resp.status_code == 200
    task_id = task_resp.json()["task_id"]

    failed_resp = client.post("/api/code-change/worker/run-once")
    assert failed_resp.status_code == 200
    assert failed_resp.json()["status"] == "FAILED"

    retry_resp = client.post(f"/api/code-change/projects/demo/tasks/{task_id}/retry")
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "QUEUED"

    metrics_resp = client.get("/api/code-change/metrics?project_id=demo")
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["queue_depth"] == 1

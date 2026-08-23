import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers import code_change
from deerflow.code_change.store import CodeChangeStore


@pytest.fixture(autouse=True)
def enable_code_change(monkeypatch):
    monkeypatch.setenv("DEER_FLOW_CODE_CHANGE_ENABLED", "true")
    monkeypatch.setenv("DEER_FLOW_CODE_CHANGE_WORKER_TOKEN", "test-worker-token")


def worker_headers() -> dict[str, str]:
    return {"X-Code-Change-Worker-Token": "test-worker-token"}


def make_client(store: CodeChangeStore, test_command: str) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[code_change.get_code_change_store] = lambda: store
    app.dependency_overrides[code_change.get_code_change_test_profiles] = lambda: {"test-profile": test_command}
    app.include_router(code_change.router)
    return TestClient(app)


def test_code_change_router_runs_patch_task(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})

    store = CodeChangeStore(tmp_path / "state")
    client = make_client(store, "python3 -c \"import app; assert app.health() == 'ok'; print('tests ok')\"")

    create_resp = client.post(
        "/api/code-change/projects",
        json={
            "name": "demo",
            "repo_path": str(repo),
            "test_profile": "test-profile",
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

    list_resp = client.get("/api/code-change/projects/demo/tasks")
    assert list_resp.status_code == 200
    assert [item["task_id"] for item in list_resp.json()["tasks"]] == [task["task_id"]]

    assert client.post("/api/code-change/worker/run-once").status_code == 403
    worker_resp = client.post("/api/code-change/worker/run-once", headers=worker_headers())
    assert worker_resp.status_code == 200
    task = worker_resp.json()
    assert task["status"] == "HANDOFF_READY"
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
    assert detail_resp.json()["status"] == "HANDOFF_READY"

    report_resp = client.get(f"/api/code-change/projects/demo/tasks/{task_id}/report")
    assert report_resp.status_code == 200
    assert "Code Change Task Report" in report_resp.text

    pr_resp = client.get(f"/api/code-change/projects/demo/tasks/{task_id}/pr-body")
    assert pr_resp.status_code == 200
    assert "Result: `PASS`" in pr_resp.text

    approval_resp = client.post(
        f"/api/code-change/projects/demo/tasks/{task_id}/review",
        json={"decision": "approve", "note": "patch and tests reviewed"},
    )
    assert approval_resp.status_code == 200
    assert approval_resp.json()["status"] == "APPROVED"
    assert approval_resp.json()["approved_by"] == "default"
    assert Path(approval_resp.json()["approval_path"]).exists()

    timeline_resp = client.get("/api/code-change/projects/demo/timeline")
    assert timeline_resp.status_code == 200
    assert len(timeline_resp.json()["events"]) >= 2

    metrics_resp = client.get("/api/code-change/metrics?project_id=demo")
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["status_counts"]["APPROVED"] == 1


def test_code_change_router_retries_failed_task(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})

    store = CodeChangeStore(tmp_path / "state")
    client = make_client(store, "python3 -c \"print('tests ok')\"")

    assert (
        client.post(
            "/api/code-change/projects",
            json={
                "name": "demo",
                "repo_path": str(repo),
                "test_profile": "test-profile",
            },
        ).status_code
        == 200
    )

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

    failed_resp = client.post("/api/code-change/worker/run-once", headers=worker_headers())
    assert failed_resp.status_code == 200
    assert failed_resp.json()["status"] == "FAILED"

    retry_resp = client.post(f"/api/code-change/projects/demo/tasks/{task_id}/retry")
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "QUEUED"

    metrics_resp = client.get("/api/code-change/metrics?project_id=demo")
    assert metrics_resp.status_code == 200
    assert metrics_resp.json()["queue_depth"] == 1


def test_code_change_router_rejects_http_test_command(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "print('ok')\n"})
    client = make_client(CodeChangeStore(tmp_path / "state"), f'{sys.executable} -c "print(1)"')

    response = client.post(
        "/api/code-change/projects",
        json={"name": "demo", "repo_path": str(repo), "test_command": f'{sys.executable} -c "print(1)"'},
    )

    assert response.status_code == 422


def test_code_change_router_is_disabled_by_default(tmp_path, committed_repo, monkeypatch):
    committed_repo({"app.py": "print('ok')\n"})
    monkeypatch.delenv("DEER_FLOW_CODE_CHANGE_ENABLED", raising=False)
    client = make_client(CodeChangeStore(tmp_path / "state"), f'{sys.executable} -c "print(1)"')

    response = client.get("/api/code-change/projects")

    assert response.status_code == 404


def test_code_change_router_resubmits_changes_requested_patch(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})
    store = CodeChangeStore(tmp_path / "state")
    client = make_client(store, "python3 -c \"import app; assert app.health() == 'ok'\"")
    assert (
        client.post(
            "/api/code-change/projects",
            json={"name": "demo", "repo_path": str(repo), "test_profile": "test-profile"},
        ).status_code
        == 200
    )
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""
    task = client.post("/api/code-change/projects/demo/tasks", json={"requirement": "fix health", "patch_text": patch}).json()
    finished = client.post("/api/code-change/worker/run-once", headers=worker_headers()).json()
    assert finished["status"] == "HANDOFF_READY"
    requested = client.post(
        f"/api/code-change/projects/demo/tasks/{task['task_id']}/review",
        json={"decision": "request_changes", "note": "please revise"},
    ).json()
    assert requested["status"] == "CHANGES_REQUESTED"

    response = client.post(
        f"/api/code-change/projects/demo/tasks/{task['task_id']}/resubmit",
        json={"patch_text": patch},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "QUEUED"


def test_code_change_router_queues_real_agent_mode(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})
    client = make_client(CodeChangeStore(tmp_path / "state"), "python3 -m pytest -q")
    assert (
        client.post(
            "/api/code-change/projects",
            json={"name": "demo", "repo_path": str(repo), "test_profile": "test-profile"},
        ).status_code
        == 200
    )

    response = client.post(
        "/api/code-change/projects/demo/tasks",
        json={"requirement": "fix health", "patch_mode": "agent", "agent_model_name": "configured-model"},
    )

    assert response.status_code == 200
    task = response.json()
    assert task["status"] == "QUEUED"
    assert task["patch_mode"] == "agent"
    assert task["agent_model_name"] == "configured-model"
    assert task["agent_thread_id"].startswith("code-change-task_")
    assert task["agent_run_id"].startswith("agent-run-")


def test_code_change_router_resubmits_patch_required_task(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})
    store = CodeChangeStore(tmp_path / "state")
    client = make_client(store, "python3 -c \"import app; assert app.health() == 'ok'\"")
    assert (
        client.post(
            "/api/code-change/projects",
            json={"name": "demo", "repo_path": str(repo), "test_profile": "test-profile"},
        ).status_code
        == 200
    )
    task = client.post(
        "/api/code-change/projects/demo/tasks",
        json={"requirement": "fix health"},
    ).json()
    failed = client.post("/api/code-change/worker/run-once", headers=worker_headers()).json()
    assert failed["error_code"] == "PATCH_REQUIRED"
    retry = client.post(f"/api/code-change/projects/demo/tasks/{task['task_id']}/retry")
    assert retry.status_code == 409
    assert "resubmit_patch" in retry.json()["detail"]
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""

    response = client.post(
        f"/api/code-change/projects/demo/tasks/{task['task_id']}/resubmit",
        json={"patch_text": patch},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "QUEUED"


def test_worker_token_must_be_explicitly_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("DEER_FLOW_CODE_CHANGE_WORKER_TOKEN", raising=False)
    client = make_client(CodeChangeStore(tmp_path / "state"), "python3 -m pytest -q")

    response = client.post("/api/code-change/worker/run-once", headers=worker_headers())

    assert response.status_code == 403

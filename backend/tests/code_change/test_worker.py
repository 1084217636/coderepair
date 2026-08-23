import sys
import threading
import time
from pathlib import Path

import pytest
from _agent_e2e_helpers import FakeToolCallingModel
from langchain_core.messages import AIMessage

from deerflow.code_change.agent_patch import AgentPatchResult
from deerflow.code_change.models import TaskStatus
from deerflow.code_change.review import review_task
from deerflow.code_change.store import CodeChangeStore, StaleTaskClaim
from deerflow.code_change.worker import create_task, resubmit_patch, retry_task, run_next_task


def test_worker_runs_queued_patch_task(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})

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
    assert len(queued.source_commit) == 40
    assert (tmp_path / "state" / "task_queue.jsonl").exists()

    finished = run_next_task(store)

    assert finished is not None
    assert finished.task_id == queued.task_id
    assert finished.status == TaskStatus.HANDOFF_READY
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
    assert metrics["status_counts"]["HANDOFF_READY"] == 1
    assert metrics["queue_depth"] == 0
    assert metrics["attempts_total"] == 1
    assert [step.name for step in finished.steps][3:6] == ["PATCH_RECEIVED", "VALIDATING_PATCH", "APPLYING_PATCH"]


def test_worker_noops_when_queue_is_empty(tmp_path):
    store = CodeChangeStore(tmp_path / "state")

    assert run_next_task(store) is None


def test_invalid_patch_is_rejected_before_task_artifact_allocation(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "print('ok')\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f'{sys.executable} -c "print(1)"')

    with pytest.raises(ValueError, match="must not be empty"):
        create_task(store, "demo", "invalid patch", patch_text="   \n", enqueue=True)

    assert list((tmp_path / "state" / "projects" / "demo" / "tasks").iterdir()) == []


def test_worker_runs_agent_generator_before_deterministic_validation(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f"{sys.executable} -c \"import app; assert app.health() == 'ok'\"")
    queued = create_task(store, "demo", "fix health", enqueue=True, patch_mode="agent", agent_model_name="fake-model")
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""

    def generate(task, workspace_path):
        assert task.task_id == queued.task_id
        assert Path(workspace_path, "app.py").read_text(encoding="utf-8").endswith("return 'bad'\n")
        return AgentPatchResult(
            patch_text=patch,
            rationale="Make the health result correct.",
            changed_files=["app.py"],
            final_message="Candidate submitted.",
            thread_id=task.agent_thread_id,
            run_id=task.agent_run_id,
        )

    finished = run_next_task(store, patch_generator=generate)

    assert finished is not None
    assert finished.status == TaskStatus.HANDOFF_READY
    assert finished.patch_mode == "agent"
    assert finished.agent_model_name == "fake-model"
    assert finished.agent_rationale == "Make the health result correct."
    step_names = [step.name for step in finished.steps]
    assert "GENERATING_PATCH" in step_names
    assert "PATCH_RECEIVED" not in step_names
    assert step_names.index("GENERATING_PATCH") < step_names.index("VALIDATING_PATCH")


def test_default_worker_agent_path_invokes_real_deerflow_graph(tmp_path, committed_repo, monkeypatch):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f"{sys.executable} -c \"import app; assert app.health() == 'ok'\"")
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""
    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "code_change_search",
                        "args": {"query": "health"},
                        "id": "search-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "code_change_submit_patch",
                        "args": {"patch_text": patch, "rationale": "Return ok."},
                        "id": "submit-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Candidate submitted."),
        ]
    )
    monkeypatch.setattr("deerflow.models.create_chat_model", lambda **_: model)
    create_task(store, "demo", "fix health", enqueue=True, patch_mode="agent", agent_model_name="fake-model")

    finished = run_next_task(store)

    assert finished is not None
    assert finished.status == TaskStatus.HANDOFF_READY
    assert finished.agent_rationale == "Return ok."
    assert finished.agent_changed_files == ["app.py"]


def test_store_claims_queued_task_for_only_one_worker(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "print('ok')\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f'{sys.executable} -c "print(1)"')
    queued = create_task(store, "demo", "claim me", enqueue=True)

    claimed = store.claim_next_task("worker-a", lease_seconds=60)

    assert claimed is not None
    assert claimed.task_id == queued.task_id
    assert claimed.worker_id == "worker-a"
    assert claimed.claim_id
    assert store.claim_next_task("worker-b", lease_seconds=60) is None

    store.release_task_claim(claimed, "worker-a", claimed.claim_id)
    reclaimed = store.claim_next_task("worker-b", lease_seconds=60)
    assert reclaimed is not None
    assert reclaimed.worker_id == "worker-b"


def test_expired_task_claim_can_be_recovered(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "print('ok')\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f'{sys.executable} -c "print(1)"')
    create_task(store, "demo", "recover me", enqueue=True)

    first = store.claim_next_task("dead-worker", lease_seconds=0)
    recovered = store.claim_next_task("healthy-worker", lease_seconds=60)

    assert first is not None
    assert recovered is not None
    assert recovered.task_id == first.task_id
    assert recovered.worker_id == "healthy-worker"
    assert recovered.claim_id != first.claim_id

    first.status = TaskStatus.FAILED
    with pytest.raises(StaleTaskClaim):
        store.save_task(first, expected_claim_id=first.claim_id)


def test_expired_unreleased_claim_does_not_block_control_plane_update(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "print('ok')\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f'{sys.executable} -c "print(1)"')
    create_task(store, "demo", "recover control plane", enqueue=True)
    claimed = store.claim_next_task("dead-worker", lease_seconds=0)
    assert claimed is not None

    claimed.error_code = "RECOVERED"
    store.save_task(claimed)

    persisted = store.get_task("demo", claimed.task_id)
    assert persisted.error_code == "RECOVERED"
    assert persisted.worker_id == ""
    assert persisted.claim_id == ""


def test_task_lookup_rejects_path_traversal(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "print('ok')\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f'{sys.executable} -c "print(1)"')

    with pytest.raises(KeyError, match="task not found"):
        store.get_task("demo", "../../projects")


def test_task_claim_can_be_renewed_only_by_current_owner(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "print('ok')\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f'{sys.executable} -c "print(1)"')
    create_task(store, "demo", "renew me", enqueue=True)
    claimed = store.claim_next_task("worker-a", lease_seconds=60)

    assert claimed is not None
    renewed = store.renew_task_claim(claimed.project_id, claimed.task_id, "worker-a", claimed.claim_id, lease_seconds=120)

    assert renewed.lease_expires_at > claimed.lease_expires_at
    with pytest.raises(StaleTaskClaim):
        store.renew_task_claim(claimed.project_id, claimed.task_id, "worker-b", claimed.claim_id, lease_seconds=120)


def test_run_next_task_heartbeats_during_long_test(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f'{sys.executable} -c "import time; time.sleep(0.7)"')
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""
    create_task(store, "demo", "fix health", patch_text=patch, enqueue=True)
    results = []

    worker = threading.Thread(target=lambda: results.append(run_next_task(store, worker_id="worker-a", lease_seconds=0.3)))
    worker.start()
    time.sleep(0.45)

    assert store.claim_next_task("worker-b", lease_seconds=1) is None
    worker.join(timeout=3)
    assert not worker.is_alive()
    assert results[0] is not None
    assert results[0].status == TaskStatus.HANDOFF_READY


def test_retry_failed_task_requeues_until_attempts_exhausted(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})

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


def test_task_without_patch_fails_with_patch_required(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'ok'\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f'{sys.executable} -c "print(1)"')

    create_task(store, "demo", "change health", enqueue=True)
    finished = run_next_task(store)

    assert finished is not None
    assert finished.status == TaskStatus.FAILED
    assert finished.error_code == "PATCH_REQUIRED"
    assert finished.test_result is None

    with pytest.raises(ValueError, match="resubmit_patch"):
        retry_task(store, "demo", finished.task_id)


def test_patch_required_task_accepts_one_revised_external_patch(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f"{sys.executable} -c \"import app; assert app.health() == 'ok'\"")
    queued = create_task(store, "demo", "fix health", enqueue=True)
    failed = run_next_task(store)
    assert failed is not None
    assert failed.error_code == "PATCH_REQUIRED"
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""

    revised = resubmit_patch(store, "demo", queued.task_id, patch_text=patch)
    finished = run_next_task(store)

    assert revised.status == TaskStatus.QUEUED
    assert revised.patch_mode == "external"
    assert finished is not None
    assert finished.status == TaskStatus.HANDOFF_READY
    assert finished.attempt_count == 2


def test_non_patch_required_failure_rejects_revised_patch(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "print('ok')\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f'{sys.executable} -c "raise SystemExit(1)"')
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-print('ok')
+print('changed')
"""
    task = create_task(store, "demo", "change app", patch_text=patch, enqueue=True)
    failed = run_next_task(store)
    assert failed is not None
    assert failed.error_code == "TEST_FAILED"

    with pytest.raises(ValueError, match="PATCH_REQUIRED"):
        resubmit_patch(store, "demo", task.task_id, patch_text=patch)


def test_changes_requested_accepts_revised_patch(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), f"{sys.executable} -c \"import app; assert app.health() == 'ok'\"")
    original_patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""
    create_task(store, "demo", "fix health", patch_text=original_patch, enqueue=True)
    finished = run_next_task(store)
    assert finished is not None
    finished = review_task(store, "demo", finished.task_id, "reviewer", "request_changes", "revise")

    revised = resubmit_patch(store, "demo", finished.task_id, patch_text=original_patch)

    assert revised.status == TaskStatus.QUEUED
    assert revised.patch_result is None
    assert revised.test_result is None
    rerun = run_next_task(store)
    assert rerun is not None
    assert rerun.status == TaskStatus.HANDOFF_READY
    assert rerun.attempt_count == 2

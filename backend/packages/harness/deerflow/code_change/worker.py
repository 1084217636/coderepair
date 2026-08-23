from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from deerflow.code_change.agent_patch import AgentPatchResult, generate_patch_with_agent
from deerflow.code_change.context_retriever import retrieve_context
from deerflow.code_change.models import PatchMode, Task, TaskStatus
from deerflow.code_change.patcher import apply_patch_text, write_pr_body
from deerflow.code_change.pr_handoff import write_pr_handoff
from deerflow.code_change.repo_scanner import scan_repo
from deerflow.code_change.report_writer import write_reports
from deerflow.code_change.state_machine import transition
from deerflow.code_change.store import CodeChangeStore, StaleTaskClaim, now_iso
from deerflow.code_change.test_runner import run_tests
from deerflow.code_change.workspace import prepare_workspace, resolve_source_commit

REQUESTED_PATCH_NAME = "requested_patch.diff"
MAX_PATCH_BYTES = 2_000_000
PatchGenerator = Callable[[Task, str], AgentPatchResult]


def create_task(
    store: CodeChangeStore,
    project_name: str,
    requirement: str,
    patch_file: str = "",
    patch_text: str = "",
    enqueue: bool = False,
    patch_mode: PatchMode | str = PatchMode.EXTERNAL,
    agent_model_name: str = "",
) -> Task:
    project = store.get_project(project_name)
    resolved_mode = PatchMode(patch_mode)
    if resolved_mode is PatchMode.AGENT and (patch_file or patch_text):
        raise ValueError("agent patch mode does not accept an external patch")
    if resolved_mode is PatchMode.EXTERNAL and agent_model_name:
        raise ValueError("agent_model_name is only valid in agent patch mode")
    patch_content = None
    if patch_file or patch_text:
        patch_content = Path(patch_file).read_text(encoding="utf-8") if patch_file else patch_text
        _validate_requested_patch(patch_content)
    source_commit = resolve_source_commit(project.repo_path)
    task_dir = store.new_task_dir(project.project_id)
    task_id = Path(task_dir).name
    task = Task(
        task_id=task_id,
        project_id=project.project_id,
        requirement=requirement,
        owner_id=store.owner_id,
        artifact_dir=str(task_dir),
        source_repo_path=project.repo_path,
        source_commit=source_commit,
        patch_mode=resolved_mode,
        agent_model_name=agent_model_name.strip(),
        agent_thread_id=f"code-change-{task_id}" if resolved_mode is PatchMode.AGENT else "",
        agent_run_id=f"agent-run-{uuid4().hex}" if resolved_mode is PatchMode.AGENT else "",
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    if patch_content is not None:
        _write_requested_patch(task_dir, patch_content)
    if enqueue:
        task.queued_at = now_iso()
        transition(task, TaskStatus.QUEUED, "Task queued for worker execution.")
        store.save_task(task)
        store.enqueue_task(task)
    return task


def execute_task(
    store: CodeChangeStore,
    task: Task,
    *,
    expected_claim_id: str | None = None,
    patch_generator: PatchGenerator | None = None,
) -> Task:
    project = store.get_project(task.project_id)
    task_dir = Path(task.artifact_dir)
    requested_patch = task_dir / REQUESTED_PATCH_NAME
    task.attempt_count += 1
    task.started_at = now_iso()
    task.finished_at = ""
    try:
        if task.status is TaskStatus.QUEUED:
            transition(task, TaskStatus.PLANNING, "Worker picked up queued task.")
        elif task.status is TaskStatus.CREATED:
            transition(task, TaskStatus.PLANNING, "Created a simple execution plan from the requirement.")

        workspace = prepare_workspace(project.repo_path, task_dir, source_commit=task.source_commit)
        task.source_repo_path = workspace.source_repo_path
        task.workspace_path = workspace.workspace_path
        task.workspace_manifest_path = workspace.manifest_path
        task.sandbox_kind = workspace.sandbox_kind
        files = scan_repo(workspace.workspace_path)
        transition(task, TaskStatus.RETRIEVING_CONTEXT, f"Scanned {len(files)} source files.")
        task.contexts = retrieve_context(workspace.workspace_path, task.requirement, files)
        if task.patch_mode is PatchMode.AGENT:
            transition(task, TaskStatus.GENERATING_PATCH, "Running the read-only DeerFlow patch-proposal Agent.")
            try:
                generated = (patch_generator or _generate_agent_patch)(task, workspace.workspace_path)
                _write_requested_patch(task_dir, generated.patch_text)
                task.agent_rationale = generated.rationale
                task.agent_changed_files = generated.changed_files
                task.agent_final_message = generated.final_message
                task.agent_thread_id = generated.thread_id
                task.agent_run_id = generated.run_id
                transition(task, TaskStatus.VALIDATING_PATCH, f"Agent submitted a typed candidate patch at {requested_patch}.")
            except Exception as exc:
                task.error_code = "AGENT_GENERATION_FAILED"
                transition(task, TaskStatus.FAILED, "Agent did not produce a valid candidate patch.", error=str(exc))
        elif not requested_patch.exists():
            task.error_code = "PATCH_REQUIRED"
            transition(
                task,
                TaskStatus.FAILED,
                "A reviewed external patch is required by the deterministic workflow.",
                error="PATCH_REQUIRED: submit a unified diff before worker execution",
            )
        else:
            transition(task, TaskStatus.PATCH_RECEIVED, f"Retrieved {len(task.contexts)} context items; external patch received.")
            transition(task, TaskStatus.VALIDATING_PATCH, f"Validating patch artifact {requested_patch}.")

        if task.status is TaskStatus.VALIDATING_PATCH:
            transition(task, TaskStatus.APPLYING_PATCH, f"Applying patch from {requested_patch} in {workspace.sandbox_kind} workspace.")
            task.patch_result = apply_patch_text(workspace.workspace_path, requested_patch.read_text(encoding="utf-8"), task_dir)
            if not task.patch_result.applied:
                task.error_code = "PATCH_APPLY_FAILED"
                transition(task, TaskStatus.FAILED, "Patch failed to apply.", error=task.patch_result.error)
        if task.status is not TaskStatus.FAILED:
            transition(task, TaskStatus.RUNNING_TESTS, f"Retrieved {len(task.contexts)} context items.")
            task.test_result = run_tests(workspace.workspace_path, project.test_command, task_dir)
            if task.test_result.passed:
                transition(task, TaskStatus.REVIEWING, "Tests passed; report is ready for human review.")
                if task.patch_result:
                    pr_body = write_pr_body(task.task_id, task.requirement, task.patch_result, True, task_dir)
                    task.pr_body_path = str(pr_body)
                    handoff = write_pr_handoff(project, task, task.patch_result, task.test_result, task_dir)
                    task.pr_handoff_path = handoff.handoff_path
                    task.pr_create_script_path = handoff.script_path
                    transition(task, TaskStatus.HANDOFF_READY, "Generated review artifacts and draft PR creation handoff.")
            else:
                task.error_code = "TEST_FAILED"
                transition(task, TaskStatus.FAILED, "Tests failed; inspect test.log.", error="test command returned non-zero exit code")
    except StaleTaskClaim:
        raise
    except Exception as exc:
        if task.status is not TaskStatus.FAILED:
            task.error_code = "TASK_EXECUTION_FAILED"
            transition(task, TaskStatus.FAILED, "Task failed.", error=str(exc))
    task.finished_at = now_iso()
    if expected_claim_id:
        store.assert_task_claim(task, task.worker_id, expected_claim_id)
    write_reports(task)
    store.save_task(task, expected_claim_id=expected_claim_id)
    return task


def run_task_now(
    store: CodeChangeStore,
    project_name: str,
    requirement: str,
    patch_file: str = "",
    patch_text: str = "",
    *,
    patch_mode: PatchMode | str = PatchMode.EXTERNAL,
    agent_model_name: str = "",
    patch_generator: PatchGenerator | None = None,
) -> Task:
    task = create_task(
        store,
        project_name,
        requirement,
        patch_file=patch_file,
        patch_text=patch_text,
        enqueue=False,
        patch_mode=patch_mode,
        agent_model_name=agent_model_name,
    )
    return execute_task(store, task, patch_generator=patch_generator)


def run_next_task(
    store: CodeChangeStore,
    worker_id: str = "",
    lease_seconds: int = 300,
    *,
    patch_generator: PatchGenerator | None = None,
) -> Task | None:
    resolved_worker_id = worker_id or f"worker-{uuid4().hex}"
    task = store.claim_next_task(resolved_worker_id, lease_seconds=lease_seconds)
    if task is None:
        return None
    claim_id = task.claim_id
    heartbeat = _TaskClaimHeartbeat(store, task, resolved_worker_id, claim_id, lease_seconds)
    heartbeat.start()
    try:
        result = execute_task(store, task, expected_claim_id=claim_id, patch_generator=patch_generator)
        heartbeat.raise_if_failed()
        return result
    finally:
        heartbeat.stop()
        store.release_task_claim(task, resolved_worker_id, claim_id)


def retry_task(store: CodeChangeStore, project_id: str, task_id: str) -> Task:
    task = store.get_task(project_id, task_id)
    if task.status is not TaskStatus.FAILED:
        raise ValueError(f"only FAILED tasks can be retried: {task.status}")
    if task.error_code == "PATCH_REQUIRED":
        raise ValueError("PATCH_REQUIRED tasks must use resubmit_patch with a unified diff")
    if task.attempt_count >= task.max_attempts:
        raise ValueError(f"retry attempts exhausted: {task.attempt_count}/{task.max_attempts}")

    task.error = ""
    task.error_code = ""
    task.queued_at = now_iso()
    transition(
        task,
        TaskStatus.QUEUED,
        f"Retry queued after failure; next attempt {task.attempt_count + 1}/{task.max_attempts}.",
    )
    store.save_task(task)
    store.enqueue_task(task)
    return task


def resubmit_patch(
    store: CodeChangeStore,
    project_id: str,
    task_id: str,
    *,
    patch_file: str = "",
    patch_text: str = "",
) -> Task:
    task = store.get_task(project_id, task_id)
    can_resubmit = task.status is TaskStatus.CHANGES_REQUESTED or (task.status is TaskStatus.FAILED and task.error_code == "PATCH_REQUIRED")
    if not can_resubmit:
        raise ValueError(f"only CHANGES_REQUESTED or PATCH_REQUIRED tasks accept a revised patch: {task.status}")
    if task.attempt_count >= task.max_attempts:
        raise ValueError(f"retry attempts exhausted: {task.attempt_count}/{task.max_attempts}")
    content = Path(patch_file).read_text(encoding="utf-8") if patch_file else patch_text
    _write_requested_patch(Path(task.artifact_dir), content)
    task.patch_mode = PatchMode.EXTERNAL
    task.agent_model_name = ""
    task.agent_thread_id = ""
    task.agent_run_id = ""
    task.agent_rationale = ""
    task.agent_changed_files = []
    task.agent_final_message = ""
    task.patch_result = None
    task.test_result = None
    task.pr_body_path = ""
    task.pr_handoff_path = ""
    task.pr_create_script_path = ""
    task.approval_path = ""
    task.approved_by = ""
    task.approval_note = ""
    task.approved_at = ""
    task.error = ""
    task.error_code = ""
    task.last_error = ""
    task.finished_at = ""
    task.queued_at = now_iso()
    transition(task, TaskStatus.QUEUED, f"Revised patch queued for attempt {task.attempt_count + 1}/{task.max_attempts}.")
    store.save_task(task)
    store.enqueue_task(task)
    return task


def _generate_agent_patch(task: Task, workspace_path: str) -> AgentPatchResult:
    """Build the configured chat model and run the restricted Agent stage."""

    from deerflow.models import create_chat_model

    model = create_chat_model(
        name=task.agent_model_name or None,
        thinking_enabled=False,
        attach_tracing=False,
    )
    return generate_patch_with_agent(
        model,
        workspace_path,
        task.requirement,
        thread_id=task.agent_thread_id,
        run_id=task.agent_run_id,
        task_id=task.task_id,
    )


def _write_requested_patch(task_dir: Path, content: str) -> None:
    encoded = _validate_requested_patch(content)
    staging = task_dir / f".{REQUESTED_PATCH_NAME}.{uuid4().hex}.tmp"
    try:
        staging.write_bytes(encoded)
        staging.replace(task_dir / REQUESTED_PATCH_NAME)
    finally:
        staging.unlink(missing_ok=True)


def _validate_requested_patch(content: str) -> bytes:
    if not content.strip():
        raise ValueError("patch content must not be empty")
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_PATCH_BYTES:
        raise ValueError(f"patch content exceeds {MAX_PATCH_BYTES} bytes")
    return encoded


class _TaskClaimHeartbeat:
    def __init__(
        self,
        store: CodeChangeStore,
        task: Task,
        worker_id: str,
        claim_id: str,
        lease_seconds: int,
    ) -> None:
        self._store = store
        self._task = task
        self._worker_id = worker_id
        self._claim_id = claim_id
        self._lease_seconds = lease_seconds
        self._interval = max(0.05, min(5.0, lease_seconds / 3)) if lease_seconds > 0 else 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: Exception | None = None

    def start(self) -> None:
        if self._interval <= 0:
            return
        self._thread = threading.Thread(target=self._run, name=f"code-change-heartbeat-{self._task.task_id}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self._interval * 2))

    def raise_if_failed(self) -> None:
        if self._error is not None:
            raise StaleTaskClaim(f"task claim heartbeat failed: {self._error}") from self._error

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._store.renew_task_claim(
                    self._task.project_id,
                    self._task.task_id,
                    self._worker_id,
                    self._claim_id,
                    lease_seconds=self._lease_seconds,
                )
            except Exception as exc:
                self._error = exc
                self._stop.set()
                return

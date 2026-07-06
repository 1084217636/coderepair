from __future__ import annotations

from pathlib import Path

from deerflow.code_change.context_retriever import retrieve_context
from deerflow.code_change.models import Task, TaskStatus
from deerflow.code_change.patcher import apply_patch_file, apply_patch_text, write_pr_body
from deerflow.code_change.repo_scanner import scan_repo
from deerflow.code_change.report_writer import write_reports
from deerflow.code_change.state_machine import transition
from deerflow.code_change.store import CodeChangeStore, now_iso
from deerflow.code_change.test_runner import run_tests


REQUESTED_PATCH_NAME = "requested_patch.diff"


def create_task(
    store: CodeChangeStore,
    project_name: str,
    requirement: str,
    patch_file: str = "",
    patch_text: str = "",
    enqueue: bool = False,
) -> Task:
    project = store.get_project(project_name)
    task_dir = store.new_task_dir(project.project_id)
    task = Task(
        task_id=Path(task_dir).name,
        project_id=project.project_id,
        requirement=requirement,
        artifact_dir=str(task_dir),
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    if patch_file or patch_text:
        patch_content = Path(patch_file).read_text(encoding="utf-8") if patch_file else patch_text
        (task_dir / REQUESTED_PATCH_NAME).write_text(patch_content, encoding="utf-8")
    if enqueue:
        task.queued_at = now_iso()
        transition(task, TaskStatus.QUEUED, "Task queued for worker execution.")
        store.save_task(task)
        store.enqueue_task(task)
    return task


def execute_task(store: CodeChangeStore, task: Task) -> Task:
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

        files = scan_repo(project.repo_path)
        transition(task, TaskStatus.RETRIEVING_CONTEXT, f"Scanned {len(files)} source files.")
        task.contexts = retrieve_context(project.repo_path, task.requirement, files)
        if requested_patch.exists():
            transition(task, TaskStatus.GENERATING_PATCH, f"Retrieved {len(task.contexts)} context items; using patch artifact.")
            transition(task, TaskStatus.APPLYING_PATCH, f"Applying patch from {requested_patch}.")
            task.patch_result = apply_patch_text(project.repo_path, requested_patch.read_text(encoding="utf-8"), task_dir)
            if not task.patch_result.applied:
                transition(task, TaskStatus.FAILED, "Patch failed to apply.", error=task.patch_result.error)
                task.finished_at = now_iso()
                write_reports(task)
                store.save_task(task)
                return task
        transition(task, TaskStatus.RUNNING_TESTS, f"Retrieved {len(task.contexts)} context items.")
        task.test_result = run_tests(project.repo_path, project.test_command, task_dir)
        if task.test_result.passed:
            transition(task, TaskStatus.REVIEWING, "Tests passed; report is ready for human review.")
            if task.patch_result:
                pr_body = write_pr_body(task.task_id, task.requirement, task.patch_result, True, task_dir)
                task.pr_body_path = str(pr_body)
                transition(task, TaskStatus.PR_CREATED, "Generated PR draft with diff explanation and test result.")
        else:
            transition(task, TaskStatus.FAILED, "Tests failed; inspect test.log.", error="test command returned non-zero exit code")
    except Exception as exc:
        if task.status is not TaskStatus.FAILED:
            transition(task, TaskStatus.FAILED, "Task failed.", error=str(exc))
    task.finished_at = now_iso()
    write_reports(task)
    store.save_task(task)
    return task


def run_task_now(store: CodeChangeStore, project_name: str, requirement: str, patch_file: str = "", patch_text: str = "") -> Task:
    task = create_task(store, project_name, requirement, patch_file=patch_file, patch_text=patch_text, enqueue=False)
    return execute_task(store, task)


def run_next_task(store: CodeChangeStore) -> Task | None:
    for item in store.queued_items():
        try:
            task = store.get_task(item["project_id"], item["task_id"])
        except KeyError:
            continue
        if task.status is TaskStatus.QUEUED:
            return execute_task(store, task)
    return None


def retry_task(store: CodeChangeStore, project_id: str, task_id: str) -> Task:
    task = store.get_task(project_id, task_id)
    if task.status is not TaskStatus.FAILED:
        raise ValueError(f"only FAILED tasks can be retried: {task.status}")
    if task.attempt_count >= task.max_attempts:
        raise ValueError(f"retry attempts exhausted: {task.attempt_count}/{task.max_attempts}")

    task.error = ""
    task.queued_at = now_iso()
    transition(
        task,
        TaskStatus.QUEUED,
        f"Retry queued after failure; next attempt {task.attempt_count + 1}/{task.max_attempts}.",
    )
    store.save_task(task)
    store.enqueue_task(task)
    return task

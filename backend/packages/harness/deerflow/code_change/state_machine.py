from __future__ import annotations

from deerflow.code_change.models import Task, TaskStatus, TaskStep
from deerflow.code_change.store import now_iso

ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.QUEUED, TaskStatus.PLANNING, TaskStatus.FAILED},
    TaskStatus.QUEUED: {TaskStatus.PLANNING, TaskStatus.FAILED},
    TaskStatus.PLANNING: {TaskStatus.RETRIEVING_CONTEXT, TaskStatus.FAILED},
    TaskStatus.RETRIEVING_CONTEXT: {
        TaskStatus.PATCH_RECEIVED,
        TaskStatus.GENERATING_PATCH,
        TaskStatus.RUNNING_TESTS,
        TaskStatus.FAILED,
    },
    TaskStatus.PATCH_RECEIVED: {TaskStatus.VALIDATING_PATCH, TaskStatus.FAILED},
    TaskStatus.VALIDATING_PATCH: {TaskStatus.APPLYING_PATCH, TaskStatus.FAILED},
    TaskStatus.GENERATING_PATCH: {TaskStatus.VALIDATING_PATCH, TaskStatus.FAILED},
    TaskStatus.APPLYING_PATCH: {TaskStatus.RUNNING_TESTS, TaskStatus.FAILED, TaskStatus.ROLLED_BACK},
    TaskStatus.RUNNING_TESTS: {TaskStatus.REVIEWING, TaskStatus.FAILED},
    TaskStatus.REVIEWING: {TaskStatus.HANDOFF_READY, TaskStatus.FAILED},
    TaskStatus.HANDOFF_READY: {TaskStatus.APPROVED, TaskStatus.CHANGES_REQUESTED},
    TaskStatus.APPROVED: {TaskStatus.PR_CREATED},
    TaskStatus.CHANGES_REQUESTED: set(),
    TaskStatus.PR_CREATED: set(),
    TaskStatus.FAILED: {TaskStatus.QUEUED},
    TaskStatus.ROLLED_BACK: set(),
}


class InvalidTransition(ValueError):
    pass


def transition(task: Task, next_status: TaskStatus, summary: str = "", error: str = "") -> None:
    allowed = ALLOWED_TRANSITIONS.get(task.status, set())
    if next_status not in allowed:
        raise InvalidTransition(f"cannot transition {task.status} -> {next_status}")
    task.status = next_status
    task.updated_at = now_iso()
    task.steps.append(
        TaskStep(
            name=str(next_status),
            status="FAILED" if next_status is TaskStatus.FAILED else "SUCCEEDED",
            summary=summary,
            error=error,
            started_at=task.updated_at,
            finished_at=task.updated_at,
        )
    )
    if error:
        task.error = error
        task.last_error = error

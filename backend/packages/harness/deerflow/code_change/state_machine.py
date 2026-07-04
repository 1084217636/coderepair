from __future__ import annotations

from deerflow.code_change.models import Task, TaskStatus, TaskStep
from deerflow.code_change.store import now_iso


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.PLANNING, TaskStatus.FAILED},
    TaskStatus.PLANNING: {TaskStatus.RETRIEVING_CONTEXT, TaskStatus.FAILED},
    TaskStatus.RETRIEVING_CONTEXT: {TaskStatus.RUNNING_TESTS, TaskStatus.FAILED},
    TaskStatus.RUNNING_TESTS: {TaskStatus.REVIEWING, TaskStatus.FAILED},
    TaskStatus.REVIEWING: set(),
    TaskStatus.FAILED: set(),
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

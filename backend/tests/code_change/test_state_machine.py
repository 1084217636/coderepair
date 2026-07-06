import pytest

from deerflow.code_change.models import Task, TaskStatus
from deerflow.code_change.state_machine import InvalidTransition, transition


def test_state_machine_allows_ordered_progression():
    task = Task(task_id="t1", project_id="demo", requirement="run tests")
    transition(task, TaskStatus.QUEUED, "queued")
    transition(task, TaskStatus.PLANNING, "plan")
    transition(task, TaskStatus.RETRIEVING_CONTEXT, "retrieve")
    transition(task, TaskStatus.GENERATING_PATCH, "generate")
    transition(task, TaskStatus.APPLYING_PATCH, "apply")
    transition(task, TaskStatus.RUNNING_TESTS, "test")
    transition(task, TaskStatus.REVIEWING, "review")
    transition(task, TaskStatus.PR_CREATED, "pr")

    assert task.status == TaskStatus.PR_CREATED
    assert [step.name for step in task.steps] == [
        "QUEUED",
        "PLANNING",
        "RETRIEVING_CONTEXT",
        "GENERATING_PATCH",
        "APPLYING_PATCH",
        "RUNNING_TESTS",
        "REVIEWING",
        "PR_CREATED",
    ]


def test_state_machine_rejects_skipped_stage():
    task = Task(task_id="t1", project_id="demo", requirement="run tests")

    with pytest.raises(InvalidTransition):
        transition(task, TaskStatus.REVIEWING)

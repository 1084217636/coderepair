import pytest

from deerflow.code_change.models import Task, TaskStatus
from deerflow.code_change.state_machine import InvalidTransition, transition


def test_state_machine_allows_ordered_progression():
    task = Task(task_id="t1", project_id="demo", requirement="run tests")
    transition(task, TaskStatus.QUEUED, "queued")
    transition(task, TaskStatus.PLANNING, "plan")
    transition(task, TaskStatus.RETRIEVING_CONTEXT, "retrieve")
    transition(task, TaskStatus.PATCH_RECEIVED, "receive")
    transition(task, TaskStatus.VALIDATING_PATCH, "validate")
    transition(task, TaskStatus.APPLYING_PATCH, "apply")
    transition(task, TaskStatus.RUNNING_TESTS, "test")
    transition(task, TaskStatus.REVIEWING, "review")
    transition(task, TaskStatus.HANDOFF_READY, "handoff")

    assert task.status == TaskStatus.HANDOFF_READY
    assert [step.name for step in task.steps] == [
        "QUEUED",
        "PLANNING",
        "RETRIEVING_CONTEXT",
        "PATCH_RECEIVED",
        "VALIDATING_PATCH",
        "APPLYING_PATCH",
        "RUNNING_TESTS",
        "REVIEWING",
        "HANDOFF_READY",
    ]


def test_state_machine_reserves_pr_created_for_external_success():
    task = Task(task_id="t1", project_id="demo", requirement="run tests", status=TaskStatus.HANDOFF_READY)

    transition(task, TaskStatus.PR_CREATED, "GitHub confirmed draft PR creation")

    assert task.status == TaskStatus.PR_CREATED


def test_state_machine_rejects_skipped_stage():
    task = Task(task_id="t1", project_id="demo", requirement="run tests")

    with pytest.raises(InvalidTransition):
        transition(task, TaskStatus.REVIEWING)


def test_state_machine_allows_failed_task_retry_queue():
    task = Task(task_id="t1", project_id="demo", requirement="run tests")

    transition(task, TaskStatus.FAILED, "failed", error="boom")
    transition(task, TaskStatus.QUEUED, "retry")

    assert task.status == TaskStatus.QUEUED
    assert task.last_error == "boom"

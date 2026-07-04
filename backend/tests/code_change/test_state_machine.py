import pytest

from deerflow.code_change.models import Task, TaskStatus
from deerflow.code_change.state_machine import InvalidTransition, transition


def test_state_machine_allows_ordered_progression():
    task = Task(task_id="t1", project_id="demo", requirement="run tests")
    transition(task, TaskStatus.PLANNING, "plan")
    transition(task, TaskStatus.RETRIEVING_CONTEXT, "retrieve")

    assert task.status == TaskStatus.RETRIEVING_CONTEXT
    assert [step.name for step in task.steps] == ["PLANNING", "RETRIEVING_CONTEXT"]


def test_state_machine_rejects_skipped_stage():
    task = Task(task_id="t1", project_id="demo", requirement="run tests")

    with pytest.raises(InvalidTransition):
        transition(task, TaskStatus.REVIEWING)

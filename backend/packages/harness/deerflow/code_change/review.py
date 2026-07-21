from __future__ import annotations

import json
from pathlib import Path

from deerflow.code_change.models import Task, TaskStatus
from deerflow.code_change.state_machine import transition
from deerflow.code_change.store import CodeChangeStore, now_iso


def review_task(
    store: CodeChangeStore,
    project_id: str,
    task_id: str,
    reviewer_id: str,
    decision: str,
    note: str = "",
) -> Task:
    task = store.get_task(project_id, task_id)
    normalized = decision.strip().lower()
    if task.status is not TaskStatus.HANDOFF_READY:
        raise ValueError(f"only HANDOFF_READY tasks can be reviewed: {task.status}")
    if normalized not in {"approve", "request_changes"}:
        raise ValueError("decision must be approve or request_changes")
    if not reviewer_id.strip():
        raise ValueError("reviewer_id is required")

    reviewed_at = now_iso()
    next_status = TaskStatus.APPROVED if normalized == "approve" else TaskStatus.CHANGES_REQUESTED
    transition(task, next_status, f"Human review decision: {normalized}.")
    task.approved_by = reviewer_id if next_status is TaskStatus.APPROVED else ""
    task.approved_at = reviewed_at if next_status is TaskStatus.APPROVED else ""
    task.approval_note = note.strip()
    approval_path = Path(task.artifact_dir) / "human_review.json"
    approval_path.write_text(
        json.dumps(
            {
                "task_id": task.task_id,
                "project_id": task.project_id,
                "reviewer_id": reviewer_id,
                "decision": normalized,
                "note": task.approval_note,
                "reviewed_at": reviewed_at,
                "resulting_status": str(next_status),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    task.approval_path = str(approval_path)
    store.save_task(task)
    return task

"""Project-level code-change workflow API.

This router exposes the local DeerFlow二开 `code_change` workflow as HTTP
endpoints, so the project can be demonstrated as an internal engineering
platform rather than only a CLI tool.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from deerflow.code_change.store import CodeChangeStore
from deerflow.code_change.worker import create_task, retry_task, run_next_task, run_task_now

router = APIRouter(prefix="/api/code-change", tags=["code-change"])


def get_code_change_store() -> CodeChangeStore:
    from deerflow.runtime.user_context import get_effective_user_id

    return CodeChangeStore(owner_id=get_effective_user_id())


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    repo_path: str = Field(..., min_length=1)
    test_command: str = Field(..., min_length=1)
    repo_url: str = ""
    default_branch: str = "main"


class TaskRunRequest(BaseModel):
    requirement: str = Field(..., min_length=1)
    patch_text: str = Field(default="", description="Unified diff content to apply before running tests")
    run_now: bool = Field(default=False, description="Run synchronously for local demos; default enqueues for worker execution")


@router.post("/projects", summary="Create Code Change Project")
def create_project(request: ProjectCreateRequest, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    try:
        project = store.create_project(
            request.name,
            request.repo_path,
            request.test_command,
            repo_url=request.repo_url,
            default_branch=request.default_branch,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return project.to_dict()


@router.get("/projects", summary="List Code Change Projects")
def list_projects(store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    return {"projects": [project.to_dict() for project in store.list_projects()]}


@router.get("/projects/{project_id}", summary="Get Code Change Project")
def get_project(project_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    try:
        return store.get_project(project_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/timeline", summary="Get Project Timeline")
def get_project_timeline(project_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    project = get_project(project_id, store)
    timeline_path = store.project_dir(project["project_id"]) / "timeline.jsonl"
    if not timeline_path.exists():
        return {"events": []}
    events = [json.loads(line) for line in timeline_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {"events": events}


@router.post("/projects/{project_id}/tasks", summary="Run Code Change Task")
def run_project_task(project_id: str, request: TaskRunRequest, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    try:
        if request.run_now:
            task = run_task_now(store, project_id, request.requirement, patch_text=request.patch_text)
        else:
            task = create_task(store, project_id, request.requirement, patch_text=request.patch_text, enqueue=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return task.to_dict()


@router.post("/worker/run-once", summary="Run One Queued Code Change Task")
def run_worker_once(store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    task = run_next_task(store)
    if task is None:
        return {"status": "NOOP"}
    return task.to_dict()


@router.get("/metrics", summary="Get Code Change Worker Metrics")
def get_worker_metrics(project_id: str = "", store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    return store.task_metrics(project_id or None)


@router.get("/projects/{project_id}/tasks/{task_id}", summary="Get Code Change Task")
def get_project_task(project_id: str, task_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    task_path = store.project_dir(project_id) / "tasks" / task_id / "task.json"
    if not task_path.exists():
        raise HTTPException(status_code=404, detail=f"task not found: {task_id}")
    return json.loads(task_path.read_text(encoding="utf-8"))


@router.post("/projects/{project_id}/tasks/{task_id}/retry", summary="Retry Failed Code Change Task")
def retry_project_task(project_id: str, task_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    try:
        task = retry_task(store, project_id, task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return task.to_dict()


@router.get(
    "/projects/{project_id}/tasks/{task_id}/report",
    response_class=PlainTextResponse,
    summary="Get Code Change Task Report",
)
def get_project_task_report(project_id: str, task_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> str:
    report_path = store.project_dir(project_id) / "tasks" / task_id / "task_report.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"task report not found: {task_id}")
    return report_path.read_text(encoding="utf-8")


@router.get(
    "/projects/{project_id}/tasks/{task_id}/pr-body",
    response_class=PlainTextResponse,
    summary="Get Code Change PR Draft",
)
def get_project_task_pr_body(project_id: str, task_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> str:
    pr_body_path = store.project_dir(project_id) / "tasks" / task_id / "pr_body.md"
    if not pr_body_path.exists():
        raise HTTPException(status_code=404, detail=f"PR body not found: {task_id}")
    return pr_body_path.read_text(encoding="utf-8")

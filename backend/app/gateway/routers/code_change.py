"""Project-level code-change workflow API.

This router exposes the local DeerFlow二开 `code_change` workflow as HTTP
endpoints, so the project can be demonstrated as an internal engineering
platform rather than only a CLI tool.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.gateway.code_change_worker_auth import is_code_change_worker_request
from app.gateway.internal_auth import get_trusted_internal_owner_user_id
from deerflow.code_change.review import review_task
from deerflow.code_change.store import CodeChangeStore
from deerflow.code_change.test_profiles import load_test_profiles
from deerflow.code_change.worker import MAX_PATCH_BYTES, create_task, resubmit_patch, retry_task, run_next_task

CODE_CHANGE_ENABLED_ENV_VAR = "DEER_FLOW_CODE_CHANGE_ENABLED"


def is_code_change_enabled() -> bool:
    return os.getenv(CODE_CHANGE_ENABLED_ENV_VAR, "false").strip().lower() in {"1", "true", "yes", "on"}


def require_code_change_enabled() -> None:
    if not is_code_change_enabled():
        raise HTTPException(status_code=404, detail="Code Change API is disabled")


router = APIRouter(prefix="/api/code-change", tags=["code-change"], dependencies=[Depends(require_code_change_enabled)])


def get_code_change_store(request: Request) -> CodeChangeStore:
    from deerflow.runtime.user_context import get_effective_user_id

    owner_id = get_trusted_internal_owner_user_id(request) or get_effective_user_id()
    return CodeChangeStore(owner_id=owner_id)


def get_code_change_test_profiles() -> dict[str, str]:
    try:
        return load_test_profiles()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="Code Change test profiles are misconfigured") from exc


def require_internal_worker(request: Request) -> None:
    if not is_code_change_worker_request(request):
        raise HTTPException(status_code=403, detail="Dedicated Code Change worker token required")


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    repo_path: str = Field(..., min_length=1)
    test_profile: str = Field(..., min_length=1, max_length=100)
    repo_url: str = ""
    default_branch: str = "main"


class TaskRunRequest(BaseModel):
    requirement: str = Field(..., min_length=1, max_length=8_000)
    patch_text: str = Field(default="", max_length=MAX_PATCH_BYTES, description="Unified diff content to apply before running tests")
    patch_mode: Literal["external", "agent"] = "external"
    agent_model_name: str = Field(default="", max_length=100)


class TaskResubmitRequest(BaseModel):
    patch_text: str = Field(..., min_length=1, max_length=MAX_PATCH_BYTES)


class TaskReviewRequest(BaseModel):
    decision: str = Field(..., pattern="^(approve|request_changes)$")
    note: str = Field(default="", max_length=2000)


@router.post("/projects", summary="Create Code Change Project")
def create_project(
    request: ProjectCreateRequest,
    store: CodeChangeStore = Depends(get_code_change_store),
    test_profiles: dict[str, str] = Depends(get_code_change_test_profiles),
) -> dict:
    try:
        test_command = test_profiles[request.test_profile]
        project = store.create_project(
            request.name,
            request.repo_path,
            test_command,
            repo_url=request.repo_url,
            default_branch=request.default_branch,
            test_profile=request.test_profile,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"unknown test_profile: {request.test_profile}") from exc
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
        task = create_task(
            store,
            project_id,
            request.requirement,
            patch_text=request.patch_text,
            enqueue=True,
            patch_mode=request.patch_mode,
            agent_model_name=request.agent_model_name,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return task.to_dict()


@router.post("/worker/run-once", summary="Run One Queued Code Change Task")
def run_worker_once(request: Request, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    require_internal_worker(request)
    task = run_next_task(store)
    if task is None:
        return {"status": "NOOP"}
    return task.to_dict()


@router.get("/metrics", summary="Get Code Change Worker Metrics")
def get_worker_metrics(project_id: str = "", store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    return store.task_metrics(project_id or None)


@router.get("/projects/{project_id}/tasks", summary="List Code Change Tasks")
def list_project_tasks(project_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    try:
        store.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    tasks = sorted(store.list_tasks(project_id), key=lambda task: task.created_at, reverse=True)
    return {"tasks": [task.to_dict() for task in tasks]}


@router.get("/projects/{project_id}/tasks/{task_id}", summary="Get Code Change Task")
def get_project_task(project_id: str, task_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    try:
        return store.get_task(project_id, task_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/tasks/{task_id}/retry", summary="Retry Failed Code Change Task")
def retry_project_task(project_id: str, task_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> dict:
    try:
        task = retry_task(store, project_id, task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return task.to_dict()


@router.post("/projects/{project_id}/tasks/{task_id}/resubmit", summary="Submit Revised Code Change Patch")
def resubmit_project_task(
    project_id: str,
    task_id: str,
    request: TaskResubmitRequest,
    store: CodeChangeStore = Depends(get_code_change_store),
) -> dict:
    try:
        task = resubmit_patch(store, project_id, task_id, patch_text=request.patch_text)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return task.to_dict()


@router.post("/projects/{project_id}/tasks/{task_id}/review", summary="Review Code Change Handoff")
def review_project_task(
    project_id: str,
    task_id: str,
    request: TaskReviewRequest,
    store: CodeChangeStore = Depends(get_code_change_store),
) -> dict:
    try:
        task = review_task(store, project_id, task_id, store.owner_id, request.decision, request.note)
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
    try:
        task = store.get_task(project_id, task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    report_path = Path(task.artifact_dir) / "task_report.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail=f"task report not found: {task_id}")
    return report_path.read_text(encoding="utf-8")


@router.get(
    "/projects/{project_id}/tasks/{task_id}/pr-body",
    response_class=PlainTextResponse,
    summary="Get Code Change PR Draft",
)
def get_project_task_pr_body(project_id: str, task_id: str, store: CodeChangeStore = Depends(get_code_change_store)) -> str:
    try:
        task = store.get_task(project_id, task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    pr_body_path = Path(task.artifact_dir) / "pr_body.md"
    if not pr_body_path.exists():
        raise HTTPException(status_code=404, detail=f"PR body not found: {task_id}")
    return pr_body_path.read_text(encoding="utf-8")

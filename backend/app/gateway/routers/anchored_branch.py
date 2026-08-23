"""Anchored Branch API.

The Gateway continues to use DeerFlow's Thread/Run/SSE endpoints.  This router
only creates a child Thread, builds request-scoped branch context, and stores a
structured human decision for an explicit Apply-to-Main action.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.base import empty_checkpoint
from pydantic import BaseModel, Field

from app.gateway.deps import get_checkpointer, get_run_manager, get_stream_bridge, get_thread_store
from app.gateway.routers.thread_runs import RunCreateRequest
from app.gateway.services import sse_consumer, start_run
from deerflow.anchored_branch import AnchoredBranchStore, AnchorSelection, BranchContextBuilder, BranchDecision
from deerflow.runtime.user_context import get_effective_user_id
from deerflow.utils.messages import message_to_text
from deerflow.utils.time import now_iso

router = APIRouter(prefix="/api/anchored-branches", tags=["anchored-branch"])


class AnchorRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12_000)
    message_id: str = ""
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    file_path: str = ""
    symbol: str = ""
    code_context: str = Field(default="", max_length=16_000)


class BranchCreateRequest(BaseModel):
    main_thread_id: str = Field(..., min_length=1)
    anchor: AnchorRequest
    root_summary: str = Field(default="", max_length=8_000)


class BranchDecisionRequest(BaseModel):
    summary: str = Field(..., min_length=1, max_length=8_000)
    actions: list[str] = Field(default_factory=list, max_length=20)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    rationale: str = Field(default="", max_length=8_000)


def _owner_id(request: Request) -> str:
    from app.gateway.internal_auth import get_trusted_internal_owner_user_id

    return get_trusted_internal_owner_user_id(request) or get_effective_user_id()


def _store(request: Request) -> AnchoredBranchStore:
    return AnchoredBranchStore(owner_id=_owner_id(request))


async def _require_thread(request: Request, thread_id: str) -> dict[str, Any]:
    thread_store = get_thread_store(request)
    record = await thread_store.get(thread_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    owner = _owner_id(request)
    record_owner = record.get("user_id")
    if record_owner and record_owner != owner:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    return record


async def _create_child_thread(request: Request, metadata: dict[str, Any]) -> str:
    thread_id = f"branch-thread-{uuid.uuid4().hex}"
    thread_store = get_thread_store(request)
    owner = _owner_id(request)
    kwargs = {"user_id": owner} if owner else {}
    await thread_store.create(thread_id, metadata=metadata, **kwargs)
    checkpointer = get_checkpointer(request)
    await checkpointer.aput(
        {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
        empty_checkpoint(),
        {"step": -1, "source": "input", "writes": None, "parents": {}, "created_at": now_iso(), **metadata},
        {},
    )
    return thread_id


def _get_branch(request: Request, branch_id: str):
    try:
        return _store(request).get(branch_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Branch {branch_id} not found") from exc


async def _checkpoint_values(request: Request, thread_id: str) -> dict[str, Any]:
    checkpoint = await get_checkpointer(request).aget_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}})
    if checkpoint is None:
        return {}
    return getattr(checkpoint, "checkpoint", {}).get("channel_values", {}) or {}


def _message_history(values: dict[str, Any]) -> list[str]:
    messages = values.get("messages") or []
    result: list[str] = []
    for message in messages[-20:]:
        text = message_to_text(message).strip()
        if text:
            role = getattr(message, "type", None) or (message.get("type") if isinstance(message, dict) else "message")
            result.append(f"{role}: {text[:4_000]}")
    return result


def _last_question(body: RunCreateRequest) -> str:
    messages = (body.input or {}).get("messages") if isinstance(body.input, dict) else None
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=422, detail="branch run requires input.messages")
    return message_to_text(messages[-1]).strip()


@router.post("", response_model=dict)
async def create_branch(body: BranchCreateRequest, request: Request) -> dict[str, Any]:
    await _require_thread(request, body.main_thread_id)
    anchor = AnchorSelection(**body.anchor.model_dump())
    parent_values = await _checkpoint_values(request, body.main_thread_id)
    summary = body.root_summary.strip() or str(parent_values.get("summary_text") or "")
    child_id = await _create_child_thread(
        request,
        {"branch_type": "anchored", "parent_thread_id": body.main_thread_id, "branch_status": "ACTIVE"},
    )
    record = _store(request).create(
        main_thread_id=body.main_thread_id,
        child_thread_id=child_id,
        owner_id=_owner_id(request),
        anchor=anchor,
        root_summary=summary,
    )
    return record.to_dict()


@router.get("/main/{main_thread_id}", response_model=list[dict])
async def list_branches(main_thread_id: str, request: Request) -> list[dict[str, Any]]:
    await _require_thread(request, main_thread_id)
    return [record.to_dict() for record in _store(request).list_for_main(main_thread_id)]


@router.get("/{branch_id}", response_model=dict)
async def get_branch(branch_id: str, request: Request) -> dict[str, Any]:
    record = _get_branch(request, branch_id)
    await _require_thread(request, record.main_thread_id)
    return record.to_dict()


@router.post("/{branch_id}/runs/stream")
async def stream_branch_run(branch_id: str, body: RunCreateRequest, request: Request) -> StreamingResponse:
    record = _get_branch(request, branch_id)
    await _require_thread(request, record.child_thread_id)
    values = await _checkpoint_values(request, record.child_thread_id)
    history = _message_history(values)
    builder = BranchContextBuilder()
    context = builder.build(
        record.anchor,
        root_summary=record.root_summary,
        branch_history=history,
        code_context=[record.anchor.code_context] if record.anchor.code_context else [],
        current_question=_last_question(body),
    )
    body = body.model_copy(
        update={
            "context": {
                **(body.context or {}),
                "branch_id": branch_id,
                "branch_context": {
                    "branch_id": branch_id,
                    "prompt": context.to_prompt(),
                    "estimated_tokens": context.estimated_tokens,
                    "truncated": context.truncated,
                },
            },
            "metadata": {**(body.metadata or {}), "branch_id": branch_id, "parent_thread_id": record.main_thread_id},
        }
    )
    bridge = get_stream_bridge(request)
    run_manager = get_run_manager(request)
    run = await start_run(body, record.child_thread_id, request)
    return StreamingResponse(
        sse_consumer(bridge, run, request, run_manager),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/{branch_id}/decision", response_model=dict)
async def create_branch_decision(branch_id: str, body: BranchDecisionRequest, request: Request) -> dict[str, Any]:
    record = _get_branch(request, branch_id)
    await _require_thread(request, record.main_thread_id)
    if record.decision is not None:
        return record.decision.to_dict()
    decision = BranchDecision(
        decision_id=f"decision_{uuid.uuid4().hex}",
        branch_id=branch_id,
        summary=body.summary.strip(),
        actions=[item.strip() for item in body.actions if item.strip()],
        constraints=[item.strip() for item in body.constraints if item.strip()],
        rationale=body.rationale.strip(),
    )
    _store(request).save_decision(record, decision)
    return decision.to_dict()


@router.post("/{branch_id}/apply", response_model=dict)
async def apply_branch_decision(branch_id: str, request: Request) -> dict[str, Any]:
    branch_store = _store(request)
    record = _get_branch(request, branch_id)
    await _require_thread(request, record.main_thread_id)
    if record.decision is None:
        raise HTTPException(status_code=409, detail="create a BranchDecision before applying it")
    if not record.decision.applied:
        thread_store = get_thread_store(request)
        await thread_store.update_metadata(
            record.main_thread_id,
            {"anchored_branch_decision": record.decision.to_dict(), "anchored_branch_id": record.branch_id},
        )
        await thread_store.update_metadata(record.child_thread_id, {"branch_status": "APPLIED"})
        record = branch_store.mark_applied(record, record.decision.decision_id)
        await thread_store.update_metadata(
            record.main_thread_id,
            {"anchored_branch_decision": record.decision.to_dict()},
        )
    return {"branch": record.to_dict(), "main_thread_id": record.main_thread_id, "applied": True}

"""Anchored Branch API.

The Gateway continues to use DeerFlow's Thread/Run/SSE endpoints.  This router
only creates a child Thread, validates an answer-local Anchor, and builds
request-scoped context without writing Branch history into the Main Thread.
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
from deerflow.anchored_branch import (
    AnchoredBranchStore,
    AnchorSelection,
    BranchContextBuilder,
    BranchContextStrategy,
)
from deerflow.code_change.context_retriever import build_retrieval_context, retrieve_context
from deerflow.code_change.repo_scanner import scan_repo
from deerflow.runtime.user_context import get_effective_user_id
from deerflow.utils.messages import message_to_text
from deerflow.utils.time import now_iso

router = APIRouter(prefix="/api/anchored-branches", tags=["anchored-branch"])


class AnchorRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=12_000)
    message_id: str = Field(..., min_length=1, max_length=256)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    file_path: str = ""
    symbol: str = ""
    code_context: str = Field(default="", max_length=16_000)


class BranchCreateRequest(BaseModel):
    main_thread_id: str = Field(..., min_length=1)
    anchor: AnchorRequest
    context_strategy: BranchContextStrategy = BranchContextStrategy.ANCHORED_CONTEXT
    token_budget: int = Field(default=6_000, ge=512, le=32_000)
    code_change_project_id: str = Field(default="", max_length=256)


def _owner_id(request: Request) -> str:
    from app.gateway.internal_auth import get_trusted_internal_owner_user_id

    return get_trusted_internal_owner_user_id(request) or get_effective_user_id()


def _store(request: Request) -> AnchoredBranchStore:
    return AnchoredBranchStore(owner_id=_owner_id(request))


def _code_change_store(request: Request):
    from app.gateway.routers.code_change import get_code_change_store

    return get_code_change_store(request)


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


def _message_items(values: dict[str, Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for message in values.get("messages") or []:
        text = message_to_text(message).strip()
        if text:
            result.append({"id": _message_id(message), "role": _message_role(message), "text": text})
    return result


def _message_id(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("id") or "")
    return str(getattr(message, "id", "") or "")


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("type") or message.get("role") or "message")
    return str(getattr(message, "type", "message") or "message")


def _validated_anchor(values: dict[str, Any], request: AnchorRequest) -> AnchorSelection:
    messages = values.get("messages") or []
    parent = next((message for message in messages if _message_id(message) == request.message_id), None)
    if parent is None:
        raise HTTPException(status_code=422, detail="anchor message_id does not exist in the Main Thread")
    if _message_role(parent) not in {"ai", "assistant"}:
        raise HTTPException(status_code=422, detail="an Anchor must belong to an assistant answer")

    parent_text = message_to_text(parent)
    selected = request.text.strip()
    start, end = request.start_offset, request.end_offset
    if (start is None) != (end is None):
        raise HTTPException(status_code=422, detail="start_offset and end_offset must be supplied together")
    if start is not None and end is not None and parent_text[start:end].strip() == selected:
        resolved_start, resolved_end = start, end
    else:
        matches: list[int] = []
        cursor = 0
        while (match := parent_text.find(selected, cursor)) >= 0:
            matches.append(match)
            cursor = match + max(1, len(selected))
        if not matches:
            raise HTTPException(status_code=422, detail="anchor text does not occur in the selected Main answer")
        resolved_start = min(matches, key=lambda match: abs(match - start)) if start is not None else matches[0]
        resolved_end = resolved_start + len(selected)

    return AnchorSelection(
        **request.model_dump(exclude={"start_offset", "end_offset"}),
        start_offset=resolved_start,
        end_offset=resolved_end,
    )


def _main_context_snapshot(values: dict[str, Any], anchor_message_id: str) -> tuple[str, list[str], list[str]]:
    messages = values.get("messages") or []
    entries: list[str] = []
    anchor_index = len(messages)
    for index, message in enumerate(messages):
        if _message_id(message) == anchor_message_id:
            anchor_index = index
            break
        text = message_to_text(message).strip()
        if text:
            entries.append(f"{_message_role(message)}: {text[:4_000]}")

    summary = str(values.get("summary_text") or "").strip()
    if not summary:
        user_entries = [item for item in entries if item.startswith(("human:", "user:"))]
        summary = (user_entries[-1] if user_entries else (entries[0] if entries else ""))[:4_000]

    # The snapshot is immutable Branch input. Keep the latest task turns before
    # the selected answer, but never copy that entire answer into the Branch.
    relevant = entries[max(0, len(entries) - 6) :]
    full_history = entries[:anchor_index]
    return summary, relevant, full_history


def _last_question(body: RunCreateRequest) -> str:
    messages = (body.input or {}).get("messages") if isinstance(body.input, dict) else None
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=422, detail="branch run requires input.messages")
    return message_to_text(messages[-1]).strip()


@router.post("", response_model=dict)
async def create_branch(body: BranchCreateRequest, request: Request) -> dict[str, Any]:
    await _require_thread(request, body.main_thread_id)
    parent_values = await _checkpoint_values(request, body.main_thread_id)
    anchor = _validated_anchor(parent_values, body.anchor)
    summary, relevant, main_history = _main_context_snapshot(parent_values, anchor.message_id)
    if body.code_change_project_id:
        try:
            _code_change_store(request).get_project(body.code_change_project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Code Change project not found") from exc
    child_id = await _create_child_thread(
        request,
        {"branch_type": "anchored", "parent_thread_id": body.main_thread_id, "branch_status": "ACTIVE"},
    )
    record = _store(request).create(
        main_thread_id=body.main_thread_id,
        child_thread_id=child_id,
        owner_id=_owner_id(request),
        anchor=anchor,
        main_task_summary=summary,
        relevant_main_context=relevant,
        main_history=main_history,
        code_change_project_id=body.code_change_project_id,
        context_strategy=body.context_strategy,
        token_budget=body.token_budget,
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


@router.get("/{branch_id}/messages", response_model=list[dict])
async def get_branch_messages(branch_id: str, request: Request) -> list[dict[str, str]]:
    record = _get_branch(request, branch_id)
    await _require_thread(request, record.child_thread_id)
    return _message_items(await _checkpoint_values(request, record.child_thread_id))


@router.post("/{branch_id}/runs/stream")
async def stream_branch_run(branch_id: str, body: RunCreateRequest, request: Request) -> StreamingResponse:
    record = _get_branch(request, branch_id)
    await _require_thread(request, record.child_thread_id)
    values = await _checkpoint_values(request, record.child_thread_id)
    history = _message_history(values)
    if record.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="closed Branches cannot start new runs")
    question = _last_question(body)
    code_context = [record.anchor.code_context] if record.anchor.code_context else []
    retrieval_tokens = 0
    retrieval_reasons: list[str] = []
    if record.code_change_project_id:
        try:
            project = _code_change_store(request).get_project(record.code_change_project_id)
        except KeyError as exc:
            raise HTTPException(status_code=409, detail="linked Code Change project no longer exists") from exc
        retrieved = retrieve_context(project.repo_path, question, scan_repo(project.repo_path), limit=8)
        retrieval_bundle = build_retrieval_context(
            retrieved,
            token_budget=min(2_000, max(512, record.token_budget // 3)),
        )
        code_context.append(retrieval_bundle.prompt)
        retrieval_tokens = retrieval_bundle.estimated_tokens
        retrieval_reasons = [item.reason for item in retrieval_bundle.items]

    builder = BranchContextBuilder(token_budget=record.token_budget)
    context = builder.build(
        record.anchor,
        main_task_summary=record.main_task_summary,
        relevant_main_context=record.relevant_main_context,
        main_history=record.main_history,
        branch_history=history,
        code_context=code_context,
        current_question=question,
        strategy=record.context_strategy,
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
                    "retrieval_tokens": retrieval_tokens,
                    "retrieval_reasons": retrieval_reasons,
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


@router.post("/{branch_id}/close", response_model=dict)
async def close_branch(branch_id: str, request: Request) -> dict[str, Any]:
    record = _get_branch(request, branch_id)
    await _require_thread(request, record.main_thread_id)
    record = _store(request).close(branch_id)
    await get_thread_store(request).update_metadata(record.child_thread_id, {"branch_status": "CLOSED"})
    return record.to_dict()

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.gateway.routers import anchored_branch as branch_router
from deerflow.anchored_branch import (
    AnchoredBranchStore,
    AnchorSelection,
    BranchContextBuilder,
    BranchContextStrategy,
    read_code_context,
)
from deerflow.anchored_branch.benchmark import default_cases, run_benchmark
from deerflow.anchored_branch.middleware import AnchoredBranchContextMiddleware


def test_context_builder_preserves_anchor_and_current_question_when_history_is_trimmed() -> None:
    anchor = AnchorSelection(text="delete cache instead of update cache", message_id="answer-1")
    context = BranchContextBuilder(token_budget=256).build(
        anchor,
        main_task_summary="The main task fixed stale reads.",
        relevant_main_context=["The service uses cache-aside after committing MySQL."],
        branch_history=[f"old branch message {index}" for index in range(30)],
        code_context=["cache.py: delete after write"],
        current_question="What changes under high concurrency?",
    )

    prompt = context.to_prompt()
    assert anchor.text in prompt
    assert context.current_question in prompt
    assert context.truncated is True
    assert context.estimated_tokens <= 256
    assert "<main_task_summary>" in prompt
    assert "<relevant_main_context>" in prompt


def test_context_builder_rejects_anchor_that_cannot_be_hard_preserved() -> None:
    with pytest.raises(ValueError, match="too large"):
        BranchContextBuilder(token_budget=256).build(
            AnchorSelection(text="x" * 2_000),
            current_question="why?",
        )


def test_read_code_context_rejects_path_escape_and_reads_bounded_lines(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "service.py").write_text("one\ntwo\nthree\n", encoding="utf-8")

    assert read_code_context(repo, "service.py", start_line=2, end_line=2) == "2: two"
    with pytest.raises(ValueError, match="inside the repository"):
        read_code_context(repo, "../secret.txt")


def test_anchor_is_resolved_against_one_assistant_message() -> None:
    values = {
        "messages": [
            HumanMessage(id="question-1", content="Explain cache consistency"),
            AIMessage(id="answer-1", content="Commit MySQL, then delete the cache key."),
        ]
    }
    request = branch_router.AnchorRequest(
        text="delete the cache key",
        message_id="answer-1",
        start_offset=19,
        end_offset=39,
    )

    anchor = branch_router._validated_anchor(values, request)

    assert anchor.message_id == "answer-1"
    assert anchor.start_offset == 19
    assert anchor.end_offset == 39


@pytest.mark.asyncio
async def test_close_branch_updates_child_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = AnchoredBranchStore(tmp_path / "branches", owner_id="user-1")
    record = store.create(
        main_thread_id="main-1",
        child_thread_id="child-1",
        owner_id="user-1",
        anchor=AnchorSelection(text="selected answer", message_id="answer-1"),
    )
    thread_store = SimpleNamespace(update_metadata=AsyncMock())
    monkeypatch.setattr(branch_router, "_store", lambda request: store)
    monkeypatch.setattr(branch_router, "_require_thread", AsyncMock(return_value={"thread_id": "main-1"}))
    monkeypatch.setattr(branch_router, "get_thread_store", lambda request: thread_store)

    result = await branch_router.close_branch(record.branch_id, SimpleNamespace())

    assert result["status"] == "CLOSED"
    thread_store.update_metadata.assert_awaited_once_with("child-1", {"branch_status": "CLOSED"})


@pytest.mark.asyncio
async def test_branch_run_targets_child_checkpoint_and_child_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = AnchoredBranchStore(tmp_path / "branches", owner_id="user-1")
    record = store.create(
        main_thread_id="main-1",
        child_thread_id="child-1",
        owner_id="user-1",
        anchor=AnchorSelection(text="selected answer", message_id="answer-1"),
        main_task_summary="Main task",
        relevant_main_context=["human: original requirement"],
    )
    request = SimpleNamespace()
    checkpoint_values = AsyncMock(return_value={"messages": [HumanMessage(content="previous branch question")]})
    start_run = AsyncMock(return_value=SimpleNamespace(run_id="run-1"))

    async def empty_stream():
        if False:
            yield b""

    monkeypatch.setattr(branch_router, "_get_branch", lambda request, branch_id: record)
    monkeypatch.setattr(branch_router, "_require_thread", AsyncMock(return_value={"thread_id": "child-1"}))
    monkeypatch.setattr(branch_router, "_checkpoint_values", checkpoint_values)
    monkeypatch.setattr(branch_router, "get_stream_bridge", lambda request: SimpleNamespace())
    monkeypatch.setattr(branch_router, "get_run_manager", lambda request: SimpleNamespace())
    monkeypatch.setattr(branch_router, "start_run", start_run)
    monkeypatch.setattr(branch_router, "sse_consumer", lambda *args: empty_stream())

    await branch_router.stream_branch_run(
        record.branch_id,
        branch_router.RunCreateRequest(input={"messages": [{"role": "human", "content": "follow up"}]}),
        request,
    )

    checkpoint_values.assert_awaited_once_with(request, "child-1")
    run_body, run_thread_id, run_request = start_run.await_args.args
    assert run_thread_id == "child-1"
    assert run_request is request
    assert run_body.context["branch_context"]["branch_id"] == record.branch_id


@pytest.mark.asyncio
async def test_branch_run_reuses_code_retrieval_for_linked_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.py").write_text("def validate_token(token):\n    return bool(token)\n", encoding="utf-8")
    store = AnchoredBranchStore(tmp_path / "branches", owner_id="user-1")
    record = store.create(
        main_thread_id="main-1",
        child_thread_id="child-1",
        owner_id="user-1",
        anchor=AnchorSelection(text="validate the token", message_id="answer-1"),
        main_task_summary="Review authentication",
        code_change_project_id="project-1",
    )
    request = SimpleNamespace()
    start_run = AsyncMock(return_value=SimpleNamespace(run_id="run-1"))

    async def empty_stream():
        if False:
            yield b""

    monkeypatch.setattr(branch_router, "_get_branch", lambda request, branch_id: record)
    monkeypatch.setattr(branch_router, "_require_thread", AsyncMock(return_value={"thread_id": "child-1"}))
    monkeypatch.setattr(branch_router, "_checkpoint_values", AsyncMock(return_value={"messages": []}))
    monkeypatch.setattr(
        branch_router,
        "_code_change_store",
        lambda request: SimpleNamespace(get_project=lambda project_id: SimpleNamespace(repo_path=str(repo))),
    )
    monkeypatch.setattr(branch_router, "get_stream_bridge", lambda request: SimpleNamespace())
    monkeypatch.setattr(branch_router, "get_run_manager", lambda request: SimpleNamespace())
    monkeypatch.setattr(branch_router, "start_run", start_run)
    monkeypatch.setattr(branch_router, "sse_consumer", lambda *args: empty_stream())

    await branch_router.stream_branch_run(
        record.branch_id,
        branch_router.RunCreateRequest(input={"messages": [{"role": "human", "content": "How is validate_token used?"}]}),
        request,
    )

    run_body = start_run.await_args.args[0]
    payload = run_body.context["branch_context"]
    assert "auth.py" in payload["prompt"]
    assert "validate_token" in payload["prompt"]
    assert payload["retrieval_tokens"] > 0
    assert payload["retrieval_reasons"]


def test_context_strategies_keep_branch_history_but_change_main_context() -> None:
    builder = BranchContextBuilder(token_budget=512)
    inputs = {
        "main_task_summary": "Fix a cache consistency bug.",
        "relevant_main_context": ["MySQL commits before cache invalidation."],
        "main_history": ["human: unrelated deployment question", "ai: unrelated answer"],
        "branch_history": ["human: why delete?", "ai: cache-aside avoids stale overwrite"],
        "current_question": "What happens with concurrent writers?",
    }
    anchor = AnchorSelection(text="delete cache after commit", message_id="answer-1")

    full = builder.build(anchor, strategy=BranchContextStrategy.FULL_HISTORY, **inputs).to_prompt()
    only = builder.build(anchor, strategy=BranchContextStrategy.ANCHOR_ONLY, **inputs).to_prompt()
    anchored = builder.build(anchor, strategy=BranchContextStrategy.ANCHORED_CONTEXT, **inputs).to_prompt()

    assert "unrelated deployment" in full
    assert "unrelated deployment" not in anchored
    assert "Fix a cache consistency bug" in anchored
    assert "MySQL commits" in anchored
    assert "Fix a cache consistency bug" not in only
    assert "why delete?" in full and "why delete?" in only and "why delete?" in anchored


def test_branch_store_supports_multiple_anchors_and_close_is_isolated(tmp_path: Path) -> None:
    store = AnchoredBranchStore(tmp_path / "branches", owner_id="user-1")
    first = store.create(
        main_thread_id="main-1",
        child_thread_id="child-1",
        owner_id="user-1",
        anchor=AnchorSelection(text="selected answer", message_id="answer-1", start_offset=4, end_offset=19),
        main_task_summary="Main task",
        relevant_main_context=["user: original requirement"],
    )
    second = store.create(
        main_thread_id="main-1",
        child_thread_id="child-2",
        owner_id="user-1",
        anchor=AnchorSelection(text="another fragment", message_id="answer-1", start_offset=30, end_offset=46),
    )
    closed = store.close(first.branch_id)
    again = store.close(first.branch_id)

    assert {item.branch_id for item in store.list_for_main("main-1")} == {first.branch_id, second.branch_id}
    assert closed.status == "CLOSED"
    assert again.status == "CLOSED"
    assert store.get(second.branch_id).status == "ACTIVE"


def test_branch_context_middleware_only_injects_request_scoped_branch_context() -> None:
    updates = AnchoredBranchContextMiddleware().before_model(
        {},
        SimpleNamespace(
            context={
                "branch_context": {"branch_id": "branch-1", "prompt": "anchor and question"},
            }
        ),
    )

    assert updates is not None
    assert [message.name for message in updates["messages"]] == ["anchored_branch_context"]


def test_benchmark_compares_three_strategies_without_inventing_model_accuracy() -> None:
    report = run_benchmark(default_cases(), token_budget=512)

    strategies = report["results"][0]["strategies"]
    assert set(strategies) == {"FULL_HISTORY", "ANCHOR_ONLY", "ANCHORED_CONTEXT"}
    assert all(item["answer_correct"] is None for item in strategies.values())
    assert strategies["FULL_HISTORY"]["irrelevant_context_ratio"] > strategies["ANCHORED_CONTEXT"]["irrelevant_context_ratio"]

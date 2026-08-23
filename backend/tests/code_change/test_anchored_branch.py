from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from deerflow.anchored_branch import AnchoredBranchStore, AnchorSelection, BranchContextBuilder, BranchDecision, read_code_context
from deerflow.anchored_branch.middleware import AnchoredBranchContextMiddleware


def test_context_builder_preserves_anchor_and_current_question_when_history_is_trimmed() -> None:
    anchor = AnchorSelection(text="delete cache instead of update cache", message_id="answer-1")
    context = BranchContextBuilder(token_budget=256).build(
        anchor,
        root_summary="The main task fixed stale reads.",
        branch_history=[f"old branch message {index}" for index in range(30)],
        code_context=["cache.py: delete after write"],
        current_question="What changes under high concurrency?",
    )

    prompt = context.to_prompt()
    assert anchor.text in prompt
    assert context.current_question in prompt
    assert context.truncated is True
    assert context.estimated_tokens <= 256


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


def test_branch_store_decision_apply_is_idempotent(tmp_path: Path) -> None:
    store = AnchoredBranchStore(tmp_path / "branches", owner_id="user-1")
    record = store.create(
        main_thread_id="main-1",
        child_thread_id="child-1",
        owner_id="user-1",
        anchor=AnchorSelection(text="selected answer"),
    )
    decision = BranchDecision(decision_id="decision-1", branch_id=record.branch_id, summary="Keep invalidate-after-write")
    store.save_decision(record, decision)
    applied = store.mark_applied(store.get(record.branch_id), "decision-1")
    again = store.mark_applied(store.get(record.branch_id), "decision-1")

    assert applied.status == "APPLIED"
    assert again.decision is not None and again.decision.applied is True


def test_branch_context_middleware_injects_branch_and_main_decision() -> None:
    updates = AnchoredBranchContextMiddleware().before_model(
        {},
        SimpleNamespace(
            context={
                "branch_context": {"branch_id": "branch-1", "prompt": "anchor and question"},
                "branch_decision": {"decision_id": "decision-1", "summary": "keep invalidation"},
            }
        ),
    )

    assert updates is not None
    assert [message.name for message in updates["messages"]] == [
        "anchored_branch_context",
        "anchored_branch_decision",
    ]

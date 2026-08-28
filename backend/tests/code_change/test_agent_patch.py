from __future__ import annotations

from pathlib import Path

import pytest
from _agent_e2e_helpers import FakeToolCallingModel
from langchain_core.messages import AIMessage

from deerflow.code_change.agent_patch import build_code_change_tools, generate_patch_with_agent


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def answer():\n    return 1\n", encoding="utf-8")
    return repo


def _patch() -> str:
    return """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def answer():
-    return 1
+    return 2
"""


def test_tools_reject_repository_escape(tmp_path: Path) -> None:
    tools, _ = build_code_change_tools(str(_repo(tmp_path)), "change answer")
    read_tool = next(tool for tool in tools if tool.name == "code_change_read_file")

    with pytest.raises(ValueError, match="inside the registered repository"):
        read_tool.invoke({"path": "../secret.txt", "start_line": 1, "end_line": 2})


def test_tools_reject_unindexed_repository_secret(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".env").write_text("API_KEY=must-not-enter-model-context\n", encoding="utf-8")
    tools, _ = build_code_change_tools(str(repo), "change answer")
    read_tool = next(tool for tool in tools if tool.name == "code_change_read_file")

    with pytest.raises(ValueError, match="outside the indexed code set"):
        read_tool.invoke({"path": ".env", "start_line": 1, "end_line": 2})


def test_tools_accept_one_typed_patch_submission(tmp_path: Path) -> None:
    tools, capture = build_code_change_tools(str(_repo(tmp_path)), "change answer")
    submit = next(tool for tool in tools if tool.name == "code_change_submit_patch")

    response = submit.invoke({"patch_text": _patch(), "rationale": "Return the requested value."})

    assert '"accepted": true' in response
    assert capture.patch_text == _patch()
    assert capture.changed_files == ["app.py"]
    with pytest.raises(ValueError, match="already been submitted"):
        submit.invoke({"patch_text": _patch(), "rationale": "again"})


def test_agent_can_correct_patch_after_submit_tool_validation_feedback(tmp_path: Path) -> None:
    malformed = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ malformed @@
-bad
+good
"""
    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "code_change_submit_patch",
                        "args": {"patch_text": malformed, "rationale": "first attempt"},
                        "id": "submit-bad",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "code_change_submit_patch",
                        "args": {"patch_text": _patch(), "rationale": "corrected diff"},
                        "id": "submit-good",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Corrected candidate submitted."),
        ]
    )

    result = generate_patch_with_agent(
        model,
        str(_repo(tmp_path)),
        "change answer to two",
        thread_id="thread-repair",
        run_id="run-repair",
    )

    assert result.patch_text == _patch()
    assert result.rationale == "corrected diff"


def test_real_deerflow_agent_graph_submits_candidate_patch(tmp_path: Path) -> None:
    model = FakeToolCallingModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "code_change_search",
                        "args": {"query": "answer"},
                        "id": "search-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "code_change_submit_patch",
                        "args": {"patch_text": _patch(), "rationale": "Change the return value."},
                        "id": "submit-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="Candidate submitted for deterministic validation."),
        ]
    )

    result = generate_patch_with_agent(
        model,
        str(_repo(tmp_path)),
        "change answer to two",
        thread_id="thread-1",
        run_id="run-1",
        task_id="task-1",
    )

    assert result.patch_text == _patch()
    assert result.changed_files == ["app.py"]
    assert result.thread_id == "thread-1"
    assert "deterministic validation" in result.final_message


def test_agent_must_use_patch_submission_tool(tmp_path: Path) -> None:
    model = FakeToolCallingModel(responses=[AIMessage(content="Here is some prose, but no tool call.")])

    with pytest.raises(ValueError, match="without calling code_change_submit_patch"):
        generate_patch_with_agent(
            model,
            str(_repo(tmp_path)),
            "change answer",
            thread_id="thread-2",
            run_id="run-2",
        )

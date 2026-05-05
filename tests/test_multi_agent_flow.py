"""
多智能体协同流程测试
"""

from pathlib import Path

from app import CodeRepairPlatform
from core.multi_agent import MultiAgentCoordinator
from llm.client import LLMClient


def _create_minimal_go_project(workspace: Path) -> None:
    (workspace / "go.mod").write_text(
        "module github.com/test/multiagent\n\ngo 1.21\n",
        encoding="utf-8",
    )
    (workspace / "main.go").write_text(
        "package main\n\nfunc main() {\n    println(\"old\")\n}\n",
        encoding="utf-8",
    )


def test_multi_agent_coordinator_runs_revision_round(monkeypatch):
    """reviewer 要求 revise 时，会触发一轮 implementer 修订。"""
    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    responses = iter([
        "## Root Cause\nold logic\n## Impacted Scope\nmain.go\n## Risks\nlow\n## Plan\n1. update main.go\n## Validation Steps\ngo build\n## Rollback Notes\nbackup",
        "draft implementation",
        "VERDICT: revise\n## Findings\nmissing edge case\n## Revision Guidance\nreturn full final answer\n## Final Recommendation\nrevise once",
        "revised implementation",
        "VERDICT: approve\n## Findings\nresolved\n## Revision Guidance\n\n## Final Recommendation\napprove",
    ])

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        return {
            "response": next(responses),
            "model": "fake-model",
            "stop_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(LLMClient, "call", fake_call)

    coordinator = MultiAgentCoordinator(provider="aicanapi", model="claude-sonnet-4-6")
    result = coordinator.run(
        task_type="bug_fix",
        language="go",
        user_query="修复 main.go 中的问题",
        analysis_info={"language": "go", "package": "main"},
        retrieval_results=[],
    )

    assert result["review"]["verdict"] == "approve"
    assert result["revision_count"] == 1
    assert result["final_response"] == "revised implementation"
    assert result["orchestration_backend"] == "langgraph"
    assert len(result["steps"]) == 5
    assert result["steps"][0]["role"] == "planner"
    assert result["steps"][-2]["role"] == "implementer"
    assert result["steps"][-2]["round_index"] == 1
    assert result["steps"][-1]["role"] == "reviewer"


def test_missing_reviewer_verdict_defaults_to_approve():
    """reviewer 未输出 VERDICT 时，默认 approve 而不是猜测 revise。"""
    result = MultiAgentCoordinator._parse_reviewer_output("没有发现严重问题，建议直接提交。")
    assert result["verdict"] == "approve"


def test_platform_can_run_multi_mode(monkeypatch, tmp_path):
    """主平台可以切到 multi 模式并返回多智能体结果。"""
    _create_minimal_go_project(tmp_path)
    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    responses = iter([
        "## Root Cause\nbug\n## Impacted Scope\nmain.go\n## Risks\nlow\n## Plan\n1. edit main.go\n## Validation Steps\ngo build\n## Rollback Notes\nbackup",
        "```go\npackage main\n\nfunc main() {\n    println(\"new\")\n}\n```",
        "VERDICT: approve\n## Findings\nnone\n## Revision Guidance\n\n## Final Recommendation\nship it",
    ])

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        return {
            "response": next(responses),
            "model": "fake-model",
            "stop_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(LLMClient, "call", fake_call)

    platform = CodeRepairPlatform(provider="aicanapi", model="claude-sonnet-4-6")
    result = platform.run(
        user_input="修复 main.go",
        workspace_root=str(tmp_path),
        validate=False,
        mode="multi",
    )

    assert result["execution_mode"] == "multi"
    assert result["multi_agent"] is not None
    assert result["multi_agent"]["orchestration_backend"] == "langgraph"
    assert result["multi_agent"]["review"]["verdict"] == "approve"
    assert result["multi_agent"]["revision_count"] == 0
    assert "println(\"new\")" in result["llm_response"]


def test_reviewer_mock_fallback_does_not_trigger_revision(monkeypatch):
    """reviewer 回退 mock 时，不应误触发 revise。"""
    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    responses = iter([
        "plan",
        "implementation",
        "mock review fallback",
    ])
    stop_reasons = iter(["stop", "stop", "stop", "mock"])

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        return {
            "response": next(responses),
            "model": "fake-model",
            "stop_reason": next(stop_reasons),
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(LLMClient, "call", fake_call)

    coordinator = MultiAgentCoordinator(provider="aicanapi", model="claude-sonnet-4-6")
    result = coordinator.run(
        task_type="review",
        language="python",
        user_query="审查当前实现",
        analysis_info={"language": "python"},
        retrieval_results=[],
    )

    assert result["review"]["verdict"] == "approve"
    assert result["revision_count"] == 0
    assert result["final_response"] == "implementation"


def test_multi_agent_uses_role_specific_contexts(monkeypatch):
    """planner / implementer / reviewer 应该看到不同密度的上下文。"""
    monkeypatch.setattr(LLMClient, "_init_client", lambda self: None)

    captured_prompts = []
    responses = iter(
        [
            "## Root Cause\nbug\n## Impacted Scope\nmain.go\n## Risks\nlow\n## Plan\n1. fix\n## Validation Steps\ngo build\n## Rollback Notes\nbackup",
            "implementation",
            "VERDICT: approve\n## Findings\nnone\n## Revision Guidance\n\n## Final Recommendation\nship it",
        ]
    )

    def fake_call(self, system_prompt, user_message, max_tokens=None):
        captured_prompts.append(user_message)
        return {
            "response": next(responses),
            "model": "fake-model",
            "stop_reason": "stop",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    monkeypatch.setattr(LLMClient, "call", fake_call)

    coordinator = MultiAgentCoordinator(provider="aicanapi", model="claude-sonnet-4-6")
    coordinator.run(
        task_type="bug_fix",
        language="go",
        user_query="修复 CreateUser",
        analysis_info={
            "language": "go",
            "package": "service",
            "functions": ["CreateUser", "DeleteUser", "ValidateUser"],
        },
        retrieval_results=[
            {
                "relative_path": "service/user.go",
                "language": "go",
                "text": "func CreateUser() error {\n    return nil\n}\n",
                "start_line": 10,
                "end_line": 12,
                "summary": "func CreateUser",
                "chunk_kind": "function",
                "symbol": "CreateUser",
                "score": 0.91,
            },
            {
                "relative_path": "go.mod",
                "language": "gomod",
                "text": "module github.com/test/multiagent\n\ngo 1.21\n",
                "start_line": 1,
                "end_line": 3,
                "summary": "go.mod:1",
                "chunk_kind": "window",
            },
        ],
        previous_response="旧实现摘要",
        previous_retrieval_summary="旧检索摘要",
    )

    planner_prompt, implementer_prompt, reviewer_prompt = captured_prompts

    assert "## 历史摘要" in planner_prompt
    assert "## 历史摘要" in implementer_prompt
    assert "## 历史摘要" not in reviewer_prompt
    assert len(implementer_prompt) > len(planner_prompt)

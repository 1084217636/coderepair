"""
多智能体协同编排

当前实现使用 LangGraph StateGraph 落地一个低风险的 3 角色协作链：
1. planner      - 理解需求、整理上下文、生成修复计划
2. implementer  - 给出代码修改建议或完整代码块
3. reviewer     - 审查实现，给出 approve / revise

如果 reviewer 判定需要修改，会通过条件边回到 implementer，
形成有限轮次的修订闭环。
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from core.logger import get_logger
from llm.client import LLMClient
from llm.prompt_builder import PromptBuilder

logger = get_logger(__name__)


class AgentRole(Enum):
    """多智能体角色定义"""

    PLANNER = "planner"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"


@dataclass
class AgentStep:
    """单个 agent 调用记录"""

    role: str
    round_index: int
    system_prompt: str
    user_prompt: str
    response: str
    model: str
    provider: str
    stop_reason: Optional[str] = None
    usage: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "round_index": self.round_index,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "response": self.response,
            "model": self.model,
            "provider": self.provider,
            "stop_reason": self.stop_reason,
            "usage": self.usage,
        }


class MultiAgentState(TypedDict, total=False):
    """LangGraph 共享状态。"""

    task_type: str
    language: str
    shared_context: str
    planner_context: str
    implementer_context: str
    reviewer_context: str
    steps: List[Dict[str, Any]]
    planner_output: str
    current_implementation: str
    reviewer_output: str
    review: Dict[str, Any]
    revision_count: int
    max_revision_rounds: int
    next_action: str


class MultiAgentCoordinator:
    """多智能体协调器（LangGraph 版）"""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_revision_rounds: int = 1,
    ):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_revision_rounds = max_revision_rounds
        self.logger = get_logger(__name__)
        self.graph = self._build_graph()

    def run(
        self,
        task_type: str,
        language: str,
        user_query: str,
        analysis_info: Optional[Dict[str, Any]] = None,
        retrieval_results: Optional[List[Dict[str, Any]]] = None,
        previous_response: Optional[str] = None,
        previous_retrieval_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行多智能体协同流程。"""
        role_contexts = self._build_role_contexts(
            task_type=task_type,
            language=language,
            user_query=user_query,
            analysis_info=analysis_info,
            retrieval_results=retrieval_results,
            previous_response=previous_response,
            previous_retrieval_summary=previous_retrieval_summary,
        )

        initial_state: MultiAgentState = {
            "task_type": task_type,
            "language": language,
            "shared_context": role_contexts["shared"],
            "planner_context": role_contexts["planner"],
            "implementer_context": role_contexts["implementer"],
            "reviewer_context": role_contexts["reviewer"],
            "steps": [],
            "planner_output": "",
            "current_implementation": "",
            "reviewer_output": "",
            "review": {},
            "revision_count": 0,
            "max_revision_rounds": self.max_revision_rounds,
            "next_action": "implementer",
        }
        final_state = self.graph.invoke(initial_state)

        final_step = self._find_last_step(final_state["steps"], AgentRole.IMPLEMENTER.value)
        if final_step is None:
            raise RuntimeError("multi-agent graph ended without implementer output")

        return {
            "mode": "multi",
            "orchestration_backend": "langgraph",
            "task_type": task_type,
            "language": language,
            "steps": final_state["steps"],
            "llm_config": {
                "provider": final_step["provider"],
                "model": final_step["model"],
            },
            "final_response": final_state["current_implementation"],
            "review": final_state["review"],
            "revision_count": final_state["revision_count"],
        }

    def render_trace_markdown(self, result: Dict[str, Any]) -> str:
        """将多智能体执行轨迹渲染成 Markdown，方便写入 artifacts。"""
        parts = ["# Multi-Agent Trace", ""]
        parts.append(f"- Mode: {result.get('mode')}")
        parts.append(f"- Orchestration Backend: {result.get('orchestration_backend', 'custom')}")
        parts.append(f"- Revision Count: {result.get('revision_count', 0)}")
        review = result.get("review", {})
        parts.append(f"- Reviewer Verdict: {review.get('verdict', 'unknown')}")
        parts.append("")

        for step in result.get("steps", []):
            parts.append(f"## {step['role']} (round {step['round_index']})")
            parts.append("")
            parts.append(f"- Provider: {step.get('provider')}")
            parts.append(f"- Model: {step.get('model')}")
            parts.append("")
            parts.append("### Response")
            parts.append("")
            parts.append(step.get("response", ""))
            parts.append("")

        return "\n".join(parts)

    def _build_graph(self):
        """构建 LangGraph 状态图。"""
        graph = StateGraph(MultiAgentState)
        graph.add_node(AgentRole.PLANNER.value, self._planner_node)
        graph.add_node(AgentRole.IMPLEMENTER.value, self._implementer_node)
        graph.add_node(AgentRole.REVIEWER.value, self._reviewer_node)

        graph.add_edge(START, AgentRole.PLANNER.value)
        graph.add_edge(AgentRole.PLANNER.value, AgentRole.IMPLEMENTER.value)
        graph.add_edge(AgentRole.IMPLEMENTER.value, AgentRole.REVIEWER.value)
        graph.add_conditional_edges(
            AgentRole.REVIEWER.value,
            self._route_after_review,
            {
                AgentRole.IMPLEMENTER.value: AgentRole.IMPLEMENTER.value,
                END: END,
            },
        )
        return graph.compile()

    def _planner_node(self, state: MultiAgentState) -> Dict[str, Any]:
        step = self._call_agent(
            role=AgentRole.PLANNER,
            round_index=0,
            system_prompt=self._system_prompt(
                AgentRole.PLANNER,
                state["language"],
                state["task_type"],
            ),
            user_prompt=self._planner_prompt(state["planner_context"]),
        )
        return {
            "planner_output": step.response,
            "steps": state["steps"] + [step.to_dict()],
        }

    def _implementer_node(self, state: MultiAgentState) -> Dict[str, Any]:
        round_index = state["revision_count"]
        if round_index == 0:
            user_prompt = self._implementer_prompt(
                state["implementer_context"],
                state["planner_output"],
            )
        else:
            user_prompt = self._implementer_revision_prompt(
                shared_context=state["implementer_context"],
                planner_output=state["planner_output"],
                implementer_output=state["current_implementation"],
                reviewer_output=state["reviewer_output"],
            )

        step = self._call_agent(
            role=AgentRole.IMPLEMENTER,
            round_index=round_index,
            system_prompt=self._system_prompt(
                AgentRole.IMPLEMENTER,
                state["language"],
                state["task_type"],
            ),
            user_prompt=user_prompt,
        )
        return {
            "current_implementation": step.response,
            "steps": state["steps"] + [step.to_dict()],
        }

    def _reviewer_node(self, state: MultiAgentState) -> Dict[str, Any]:
        round_index = state["revision_count"]
        step = self._call_agent(
            role=AgentRole.REVIEWER,
            round_index=round_index,
            system_prompt=self._system_prompt(
                AgentRole.REVIEWER,
                state["language"],
                state["task_type"],
            ),
            user_prompt=self._reviewer_prompt(
                state["reviewer_context"],
                state["planner_output"],
                state["current_implementation"],
            ),
        )

        review_summary = self._parse_reviewer_output(
            step.response,
            stop_reason=step.stop_reason,
        )

        next_action = END
        revision_count = state["revision_count"]
        if (
            review_summary["verdict"] == "revise"
            and state["revision_count"] < state["max_revision_rounds"]
        ):
            revision_count += 1
            next_action = AgentRole.IMPLEMENTER.value

        return {
            "reviewer_output": step.response,
            "review": review_summary,
            "revision_count": revision_count,
            "next_action": next_action,
            "steps": state["steps"] + [step.to_dict()],
        }

    @staticmethod
    def _route_after_review(state: MultiAgentState) -> str:
        return state.get("next_action", END)

    def _call_agent(
        self,
        role: AgentRole,
        round_index: int,
        system_prompt: str,
        user_prompt: str,
    ) -> AgentStep:
        """调用单个 agent。"""
        client = LLMClient(
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
        )
        self.logger.info(
            f"[MultiAgent] 调用角色 | role={role.value} | round={round_index} | "
            f"provider={client.provider} | model={client.model}"
        )
        result = client.call(system_prompt, user_prompt)
        return AgentStep(
            role=role.value,
            round_index=round_index,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response=result.get("response", ""),
            model=result.get("model", client.model),
            provider=client.provider,
            stop_reason=result.get("stop_reason"),
            usage=result.get("usage", {}),
        )

    @staticmethod
    def _system_prompt(role: AgentRole, language: str, task_type: str) -> str:
        common = (
            f"你是一个 {language} 代码协作系统中的 {role.value} agent。"
            f"当前任务类型为 {task_type}。"
            "请只完成你当前角色的职责，输出要清晰、具体、可执行。"
            "不要输出 tool_call、function call、XML 标签或伪工具调用格式。"
        )
        if role == AgentRole.PLANNER:
            return common + "你负责理解需求、整理上下文、识别风险，并生成低风险修复计划。"
        if role == AgentRole.IMPLEMENTER:
            return common + "你负责给出可落地的代码修改建议，必要时输出完整代码块。"
        return (
            common
            + "你负责审查 implementer 的输出，严格指出风险。"
            + "第一行必须输出 VERDICT: approve 或 VERDICT: revise。"
        )

    @staticmethod
    def _build_shared_context(
        task_type: str,
        language: str,
        user_query: str,
        analysis_info: Optional[Dict[str, Any]],
        retrieval_results: Optional[List[Dict[str, Any]]],
        previous_response: Optional[str],
        previous_retrieval_summary: Optional[str],
    ) -> str:
        return PromptBuilder.build_context_outline(
            user_query=user_query,
            language=language,
            analysis_info=analysis_info,
            retrieval_results=retrieval_results,
            previous_response=previous_response,
            previous_retrieval_summary=previous_retrieval_summary,
            include_history=True,
            primary_limit=2,
            supporting_limit=2,
            primary_char_limit=600,
            supporting_char_limit=280,
        )

    @classmethod
    def _build_role_contexts(
        cls,
        task_type: str,
        language: str,
        user_query: str,
        analysis_info: Optional[Dict[str, Any]],
        retrieval_results: Optional[List[Dict[str, Any]]],
        previous_response: Optional[str],
        previous_retrieval_summary: Optional[str],
    ) -> Dict[str, str]:
        shared_context = cls._build_shared_context(
            task_type=task_type,
            language=language,
            user_query=user_query,
            analysis_info=analysis_info,
            retrieval_results=retrieval_results,
            previous_response=previous_response,
            previous_retrieval_summary=previous_retrieval_summary,
        )
        planner_context = PromptBuilder.build_context_outline(
            user_query=user_query,
            language=language,
            analysis_info=analysis_info,
            retrieval_results=retrieval_results,
            previous_response=previous_response,
            previous_retrieval_summary=previous_retrieval_summary,
            include_history=True,
            primary_limit=1,
            supporting_limit=2,
            primary_char_limit=450,
            supporting_char_limit=220,
        )
        implementer_context = PromptBuilder.build_context_outline(
            user_query=user_query,
            language=language,
            analysis_info=analysis_info,
            retrieval_results=retrieval_results,
            previous_response=previous_response,
            previous_retrieval_summary=previous_retrieval_summary,
            include_history=True,
            primary_limit=2,
            supporting_limit=3,
            primary_char_limit=900,
            supporting_char_limit=450,
        )
        reviewer_context = PromptBuilder.build_context_outline(
            user_query=user_query,
            language=language,
            analysis_info=analysis_info,
            retrieval_results=retrieval_results,
            previous_response=None,
            previous_retrieval_summary=None,
            include_history=False,
            primary_limit=2,
            supporting_limit=2,
            primary_char_limit=650,
            supporting_char_limit=260,
        )

        return {
            "shared": shared_context,
            "planner": planner_context,
            "implementer": implementer_context,
            "reviewer": reviewer_context,
        }

    @staticmethod
    def _truncate(text: str, max_chars: int, label: str = "") -> str:
        """尽量在段落边界截断，避免截断在代码块或句子中间。"""
        if len(text) <= max_chars:
            return text

        cut = text.rfind("\n\n", 0, max_chars)
        if cut == -1:
            cut = max_chars

        suffix = (
            f"\n\n[{label} 内容已截断，原始长度 {len(text)} 字符]"
            if label
            else "\n\n[内容已截断]"
        )
        return text[:cut] + suffix

    @staticmethod
    def _planner_prompt(shared_context: str) -> str:
        return (
            f"{shared_context}\n\n"
            "请完成修复计划，并按下面结构输出：\n"
            "## Root Cause\n"
            "## Impacted Scope\n"
            "## Risks\n"
            "## Plan\n"
            "## Validation Steps\n"
            "## Rollback Notes\n"
        )

    @staticmethod
    def _implementer_prompt(
        shared_context: str,
        planner_output: str,
    ) -> str:
        return (
            f"{shared_context}\n\n"
            "## Planner Output\n"
            f"{MultiAgentCoordinator._truncate(planner_output, 2200, 'Planner')}\n\n"
            "请给出最终实现建议。要求：\n"
            "1. 先说明修改点\n"
            "2. 如果目标文件已足够明确，尽量输出完整代码块\n"
            "3. 说明验证方式和注意事项\n"
            "4. 不要输出任何 tool_call 或伪函数调用格式\n"
        )

    @staticmethod
    def _reviewer_prompt(
        shared_context: str,
        planner_output: str,
        implementer_output: str,
    ) -> str:
        return (
            f"{shared_context}\n\n"
            "## Planner Output\n"
            f"{MultiAgentCoordinator._truncate(planner_output, 1800, 'Planner')}\n\n"
            "## Implementer Output\n"
            f"{MultiAgentCoordinator._truncate(implementer_output, 2200, 'Implementer')}\n\n"
            "请严格审查 implementer 输出。第一行必须是：\n"
            "VERDICT: approve\n"
            "或\n"
            "VERDICT: revise\n\n"
            "随后按下面结构输出：\n"
            "## Findings\n"
            "## Revision Guidance\n"
            "## Final Recommendation\n"
        )

    @staticmethod
    def _implementer_revision_prompt(
        shared_context: str,
        planner_output: str,
        implementer_output: str,
        reviewer_output: str,
    ) -> str:
        return (
            f"{shared_context}\n\n"
            "## Planner Output\n"
            f"{MultiAgentCoordinator._truncate(planner_output, 1800, 'Planner')}\n\n"
            "## Previous Implementer Output\n"
            f"{MultiAgentCoordinator._truncate(implementer_output, 2200, 'Implementer')}\n\n"
            "## Reviewer Feedback\n"
            f"{MultiAgentCoordinator._truncate(reviewer_output, 1800, 'Reviewer')}\n\n"
            "请根据 reviewer 意见修订你的输出。保持最终答复可直接给用户使用。"
            "不要输出任何 tool_call 或伪函数调用格式。"
        )

    @staticmethod
    def _parse_reviewer_output(text: str, stop_reason: Optional[str] = None) -> Dict[str, Any]:
        """从 reviewer 输出中解析 verdict 和反馈。"""
        if stop_reason == "mock":
            return {
                "verdict": "approve",
                "feedback": text,
                "revision_guidance": "",
                "note": "reviewer_mock_fallback",
            }

        match = re.search(r"VERDICT\s*:\s*(approve|revise)", text, re.IGNORECASE)
        if match:
            verdict = match.group(1).lower()
        else:
            logger.warning("[MultiAgent] reviewer 未输出 VERDICT 标记，默认 approve")
            verdict = "approve"

        revision_guidance = ""
        guidance_match = re.search(
            r"##\s*Revision Guidance\s*(.*?)(?:##\s*Final Recommendation|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if guidance_match:
            revision_guidance = guidance_match.group(1).strip()

        return {
            "verdict": verdict,
            "feedback": text,
            "revision_guidance": revision_guidance,
        }

    @staticmethod
    def _find_last_step(steps: List[Dict[str, Any]], role: str) -> Optional[Dict[str, Any]]:
        for step in reversed(steps):
            if step.get("role") == role:
                return step
        return None

from __future__ import annotations

from typing import Any, override

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage
from langgraph.runtime import Runtime


class AnchoredBranchContextMiddleware(AgentMiddleware):
    """Inject one request-scoped branch context into the existing Agent graph."""

    @override
    def before_model(self, state: dict[str, Any], runtime: Runtime) -> dict[str, Any] | None:
        context = getattr(runtime, "context", {}) or {}
        payload = context.get("branch_context") if isinstance(context, dict) else None
        updates: list[SystemMessage] = []
        if isinstance(payload, dict):
            prompt = payload.get("prompt")
            branch_id = str(payload.get("branch_id") or context.get("branch_id") or "unknown")
            if isinstance(prompt, str) and prompt.strip():
                updates.append(
                    SystemMessage(
                        id=f"anchored-branch-context:{branch_id}",
                        name="anchored_branch_context",
                        content=prompt,
                        additional_kwargs={"hide_from_ui": True, "anchored_branch_context": True},
                    )
                )
        return {"messages": updates} if updates else None

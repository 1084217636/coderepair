from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class BranchStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class BranchContextStrategy(StrEnum):
    FULL_HISTORY = "FULL_HISTORY"
    ANCHOR_ONLY = "ANCHOR_ONLY"
    ANCHORED_CONTEXT = "ANCHORED_CONTEXT"


@dataclass(slots=True)
class AnchorSelection:
    """A user-selected fragment from a main-thread answer."""

    text: str
    message_id: str = ""
    start_offset: int | None = None
    end_offset: int | None = None
    file_path: str = ""
    symbol: str = ""
    code_context: str = ""

    def __post_init__(self) -> None:
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("anchor text must not be empty")
        if self.start_offset is not None and self.start_offset < 0:
            raise ValueError("start_offset must be non-negative")
        if self.end_offset is not None and self.end_offset < (self.start_offset or 0):
            raise ValueError("end_offset must not precede start_offset")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BranchRecord:
    branch_id: str
    main_thread_id: str
    child_thread_id: str
    owner_id: str
    anchor: AnchorSelection
    main_task_summary: str = ""
    relevant_main_context: list[str] = field(default_factory=list)
    main_history: list[str] = field(default_factory=list)
    code_change_project_id: str = ""
    context_strategy: BranchContextStrategy = BranchContextStrategy.ANCHORED_CONTEXT
    token_budget: int = 6_000
    status: BranchStatus = BranchStatus.ACTIVE
    created_at: str = ""
    updated_at: str = ""
    closed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = str(self.status)
        data["context_strategy"] = str(self.context_strategy)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BranchRecord:
        payload = dict(data)
        legacy_status = payload.get("status", BranchStatus.ACTIVE)
        payload["status"] = BranchStatus.CLOSED if legacy_status in {"APPLIED", "ARCHIVED"} else BranchStatus(legacy_status)
        payload["anchor"] = AnchorSelection(**payload["anchor"])
        payload["main_task_summary"] = payload.pop("root_summary", payload.get("main_task_summary", ""))
        payload.pop("decision", None)
        payload["context_strategy"] = BranchContextStrategy(payload.get("context_strategy", BranchContextStrategy.ANCHORED_CONTEXT))
        return cls(**payload)

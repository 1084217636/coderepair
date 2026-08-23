from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class BranchStatus(StrEnum):
    ACTIVE = "ACTIVE"
    APPLIED = "APPLIED"
    ARCHIVED = "ARCHIVED"


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
class BranchDecision:
    """Structured human decision; it is intentionally not a code mutation."""

    decision_id: str
    branch_id: str
    summary: str
    actions: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    rationale: str = ""
    applied: bool = False
    applied_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BranchRecord:
    branch_id: str
    main_thread_id: str
    child_thread_id: str
    owner_id: str
    anchor: AnchorSelection
    root_summary: str = ""
    status: BranchStatus = BranchStatus.ACTIVE
    created_at: str = ""
    updated_at: str = ""
    decision: BranchDecision | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = str(self.status)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BranchRecord:
        payload = dict(data)
        payload["status"] = BranchStatus(payload.get("status", BranchStatus.ACTIVE))
        payload["anchor"] = AnchorSelection(**payload["anchor"])
        if payload.get("decision"):
            payload["decision"] = BranchDecision(**payload["decision"])
        return cls(**payload)

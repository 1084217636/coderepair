from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .models import AnchorSelection, BranchDecision, BranchRecord, BranchStatus


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe(value: str) -> str:
    normalized = "".join(char if char.isalnum() or char in "-_" else "-" for char in value.strip())
    return normalized.strip("-_") or "default"


class AnchoredBranchStore:
    """Small owner-scoped branch index; messages remain in DeerFlow Threads."""

    def __init__(self, base_dir: str | Path | None = None, owner_id: str = "default") -> None:
        root = base_dir or Path(os.getenv("DEER_FLOW_HOME", Path.cwd() / ".deer-flow")) / "anchored-branches"
        self.owner_dir = Path(root).expanduser().resolve() / _safe(owner_id)
        self.owner_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        *,
        main_thread_id: str,
        child_thread_id: str,
        owner_id: str,
        anchor: AnchorSelection,
        root_summary: str = "",
    ) -> BranchRecord:
        branch_id = f"branch_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"
        timestamp = now_iso()
        record = BranchRecord(
            branch_id=branch_id,
            main_thread_id=main_thread_id,
            child_thread_id=child_thread_id,
            owner_id=owner_id,
            anchor=anchor,
            root_summary=root_summary,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.save(record)
        return record

    def save(self, record: BranchRecord) -> BranchRecord:
        record.updated_at = now_iso()
        destination = self.owner_dir / f"{_safe(record.branch_id)}.json"
        fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=self.owner_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return record

    def get(self, branch_id: str) -> BranchRecord:
        path = self.owner_dir / f"{_safe(branch_id)}.json"
        if not path.exists():
            raise KeyError(f"branch not found: {branch_id}")
        record = BranchRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if record.branch_id != branch_id:
            raise KeyError(f"branch not found: {branch_id}")
        return record

    def list_for_main(self, main_thread_id: str) -> list[BranchRecord]:
        records = []
        for path in self.owner_dir.glob("branch_*.json"):
            record = BranchRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
            if record.main_thread_id == main_thread_id:
                records.append(record)
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def save_decision(self, record: BranchRecord, decision: BranchDecision) -> BranchRecord:
        if record.decision and record.decision.decision_id != decision.decision_id:
            raise ValueError("branch already has a different decision")
        record.decision = decision
        return self.save(record)

    def mark_applied(self, record: BranchRecord, decision_id: str) -> BranchRecord:
        if record.decision is None or record.decision.decision_id != decision_id:
            raise ValueError("decision does not belong to branch")
        if record.decision.applied:
            return record
        record.decision.applied = True
        record.decision.applied_at = now_iso()
        record.status = BranchStatus.APPLIED
        return self.save(record)

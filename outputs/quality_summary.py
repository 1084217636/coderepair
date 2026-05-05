"""
Compact quality summary for AI-assisted development runs.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class QualitySummaryBuilder:
    """Build a resume/JD-friendly quality evaluation record."""

    @staticmethod
    def build(result: Dict[str, Any], tool_calls: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        apply_output = result.get("apply_output") or {}
        validation = result.get("validation_output") or {}
        evaluation = result.get("evaluation_output") or {}
        diff_stats = apply_output.get("diff_stats") or {}
        rollback_output = apply_output.get("rollback_output") or {}
        multi_agent = result.get("multi_agent") or {}
        review = multi_agent.get("review") or {}
        failed_tool_count = len(
            [
                item for item in (tool_calls or {}).get("calls", [])
                if item.get("status") in {"error", "failed"}
            ]
        )

        rollback_triggered = apply_output.get("status") == "rolled_back" or (
            rollback_output.get("status") == "success"
        )
        tests_passed = bool(validation.get("success"))
        manual_review_required = (
            not tests_passed
            or apply_output.get("status") in {"applied_unverified", "validate_failed", "rollback_failed"}
            or review.get("verdict") == "revise"
            or failed_tool_count > 0
        )

        return {
            "task_type": result.get("task_type"),
            "language": result.get("language"),
            "execution_mode": result.get("execution_mode"),
            "files_changed": 1 if apply_output.get("status") in {"applied", "validated", "applied_unverified", "validate_failed", "rolled_back"} else 0,
            "lines_added": diff_stats.get("additions", 0),
            "lines_deleted": diff_stats.get("deletions", 0),
            "tests_passed": tests_passed,
            "validation_source": validation.get("source"),
            "rollback_triggered": rollback_triggered,
            "manual_review_required": manual_review_required,
            "failure_reason": QualitySummaryBuilder._failure_reason(apply_output, validation),
            "retrieval_hit_rate": evaluation.get("retrieval_hit_rate"),
            "repair_status": evaluation.get("repair_status"),
            "repair_success": evaluation.get("repair_success"),
            "tool_call_count": (tool_calls or {}).get("call_count", 0),
            "failed_tool_call_count": failed_tool_count,
        }

    @staticmethod
    def _failure_reason(apply_output: Dict[str, Any], validation: Dict[str, Any]) -> Optional[str]:
        if apply_output.get("reason"):
            return apply_output["reason"]
        if validation.get("skipped_reason"):
            return validation["skipped_reason"]
        if validation and not validation.get("success"):
            stderr = (validation.get("stderr") or "").strip()
            if stderr:
                return stderr.splitlines()[0][:240]
            return f"validation_failed:{validation.get('stage', 'unknown')}"
        if apply_output.get("status") in {"rollback_failed", "validate_failed"}:
            return apply_output.get("status")
        return None

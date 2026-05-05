"""
Human-readable delivery artifacts for one CodeRepair run.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional


class TaskReportBuilder:
    """Build report, validation log, and review payload artifacts."""

    @staticmethod
    def render_validation_log(validation_output: Optional[Dict[str, Any]]) -> str:
        if not validation_output:
            return "Validation skipped.\n"

        raw = validation_output.get("raw") or {}
        parts = [
            "# Validation Log",
            "",
            f"Generated At: {datetime.now().isoformat()}",
            f"Source: {validation_output.get('source', 'unknown')}",
            f"Stage: {validation_output.get('stage', 'unknown')}",
            f"Command: {raw.get('cmd', 'n/a')}",
            f"CWD: {raw.get('cwd', 'n/a')}",
            f"Exit Code: {validation_output.get('exit_code')}",
            f"Success: {bool(validation_output.get('success'))}",
            f"Duration: {validation_output.get('duration', 0.0)}",
        ]
        if validation_output.get("timed_out"):
            parts.append("Timed Out: true")
        if validation_output.get("skipped_reason"):
            parts.append(f"Skipped Reason: {validation_output.get('skipped_reason')}")

        parts.extend(["", "## stdout", ""])
        parts.append(validation_output.get("stdout") or "")
        parts.extend(["", "## stderr", ""])
        parts.append(validation_output.get("stderr") or "")
        return "\n".join(parts).rstrip() + "\n"

    @staticmethod
    def build_review_payload(result: Dict[str, Any]) -> Dict[str, Any]:
        multi_agent = result.get("multi_agent")
        if multi_agent:
            return {
                "mode": "multi",
                "orchestration_backend": multi_agent.get("orchestration_backend"),
                "revision_count": multi_agent.get("revision_count", 0),
                "review": multi_agent.get("review", {}),
            }
        return {
            "mode": "single",
            "review": {
                "verdict": "not_run",
                "reason": "single_agent_mode",
            },
        }

    @staticmethod
    def render_task_report(
        *,
        result: Dict[str, Any],
        analysis_output: Dict[str, Any],
        retrieval_summary: Dict[str, Any],
        tool_calls: Dict[str, Any],
        artifact_names: Iterable[str],
    ) -> str:
        evaluation = result.get("evaluation_output") or {}
        apply_output = result.get("apply_output") or {}
        validation = result.get("validation_output") or {}
        rag = retrieval_summary.get("rag") or {}
        llm_config = result.get("llm_config") or {}

        parts = [
            "# CodeRepair Task Report",
            "",
            f"- Generated At: {datetime.now().isoformat()}",
            f"- Session ID: {result.get('session_id')}",
            f"- Parent Session ID: {result.get('parent_session_id') or 'none'}",
            f"- Workspace: {analysis_output.get('workspace_root', 'n/a')}",
            f"- Task Type: {result.get('task_type')}",
            f"- Language: {result.get('language')}",
            f"- Execution Mode: {result.get('execution_mode')}",
            "",
            "## Request",
            "",
            result.get("user_query") or analysis_output.get("user_query") or "",
            "",
            "## LLM",
            "",
            f"- Provider: {llm_config.get('provider', 'n/a')}",
            f"- Model: {llm_config.get('model', 'n/a')}",
            "",
            "## Repository Context",
            "",
            f"- Scanned Files: {analysis_output.get('scanned_files', 0)}",
            f"- Go Files: {analysis_output.get('go_files', 0)}",
            f"- Engineering Files: {analysis_output.get('engineering_files', 0)}",
            f"- AST Analyzed Files: {analysis_output.get('analyzed_files', 0)}",
            f"- Functions: {len(analysis_output.get('functions', []))}",
            f"- Methods: {len(analysis_output.get('methods', []))}",
            f"- Call Relations: {analysis_output.get('call_relations_count', 0)}",
            "",
            "## Retrieval",
            "",
            f"- Backend: {rag.get('backend', 'n/a')}",
            f"- Lexical Backend: {rag.get('lexical_backend', 'n/a')}",
            f"- Embedding Provider: {rag.get('provider', 'n/a')}",
            f"- Rerank Enabled: {bool(rag.get('rerank_enabled'))}",
            f"- Total Chunks: {retrieval_summary.get('total_chunks', 0)}",
            f"- Retrieved Chunks: {retrieval_summary.get('retrieved_chunks', 0)}",
            f"- Retrieved Files: {evaluation.get('retrieved_files', 0)}",
            f"- Retrieval Hit Rate: {evaluation.get('retrieval_hit_rate', 0.0)}",
            "",
            "## Patch Lifecycle",
            "",
            f"- Apply Status: {apply_output.get('status', 'analysis_only')}",
            f"- Apply File: {apply_output.get('file', 'n/a')}",
        ]

        diff_stats = apply_output.get("diff_stats") or {}
        if diff_stats:
            parts.extend(
                [
                    f"- Additions: {diff_stats.get('additions', 0)}",
                    f"- Deletions: {diff_stats.get('deletions', 0)}",
                    f"- Total Changes: {diff_stats.get('total_changes', 0)}",
                ]
            )

        rollback = apply_output.get("rollback_output")
        if rollback:
            parts.append(f"- Rollback Status: {rollback.get('status')}")
            if rollback.get("reason"):
                parts.append(f"- Rollback Reason: {rollback.get('reason')}")

        parts.extend(
            [
                "",
                "## Validation",
                "",
                f"- Source: {validation.get('source', 'n/a')}",
                f"- Stage: {validation.get('stage', 'n/a')}",
                f"- Success: {bool(validation.get('success')) if validation else False}",
                f"- Exit Code: {validation.get('exit_code', 'n/a')}",
                f"- Skipped Reason: {validation.get('skipped_reason') or 'none'}",
                "",
                "## Run Metrics",
                "",
                f"- Repair Status: {evaluation.get('repair_status', 'n/a')}",
                f"- Repair Success: {evaluation.get('repair_success', False)}",
                f"- Validation Passed: {evaluation.get('validation_passed', False)}",
                f"- Code Block Count: {evaluation.get('code_block_count', 0)}",
                f"- Tool Calls: {tool_calls.get('call_count', 0)}",
                "",
                "## Artifacts",
                "",
            ]
        )

        for artifact_name in artifact_names:
            parts.append(f"- {artifact_name}")

        return "\n".join(parts).rstrip() + "\n"

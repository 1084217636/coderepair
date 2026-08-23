from __future__ import annotations

import json
from pathlib import Path

from deerflow.code_change.models import Task


def write_reports(task: Task) -> None:
    artifact_dir = Path(task.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "task_report.md").write_text(render_task_report(task), encoding="utf-8")
    (artifact_dir / "audit.json").write_text(json.dumps(task.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_task_report(task: Task) -> str:
    lines = [
        "# Code Change Task Report",
        "",
        f"- Task ID: `{task.task_id}`",
        f"- Project: `{task.project_id}`",
        f"- Status: `{task.status}`",
        f"- Requirement: {task.requirement}",
        f"- Sandbox: `{task.sandbox_kind or 'none'}`",
        f"- Source repo: `{task.source_repo_path or 'n/a'}`",
        f"- Source commit: `{task.source_commit or 'n/a'}`",
        f"- Patch mode: `{task.patch_mode}`",
        f"- Workspace: `{task.workspace_path or 'n/a'}`",
        f"- Workspace manifest: `{task.workspace_manifest_path or 'n/a'}`",
        "",
        "## Retrieved Context",
        "",
    ]
    if task.contexts:
        for ctx in task.contexts:
            lines.append(f"- `{ctx.path}` score={ctx.score} ({ctx.reason})")
    else:
        lines.append("- No context retrieved.")

    if task.patch_mode == "agent":
        lines.extend(
            [
                "",
                "## Agent Proposal",
                "",
                f"- Model: `{task.agent_model_name or 'configured default'}`",
                f"- Thread ID: `{task.agent_thread_id or 'n/a'}`",
                f"- Run ID: `{task.agent_run_id or 'n/a'}`",
                f"- Rationale: {task.agent_rationale or 'n/a'}",
                "- Candidate files:",
            ]
        )
        lines.extend(f"  - `{path}`" for path in task.agent_changed_files)
        if not task.agent_changed_files:
            lines.append("  - None")

    lines.extend(["", "## Patch", ""])
    if task.patch_result:
        lines.extend(
            [
                f"- Applied: `{task.patch_result.applied}`",
                f"- Patch: `{task.patch_result.patch_path}`",
                f"- Additions: `{task.patch_result.lines_added}`",
                f"- Deletions: `{task.patch_result.lines_deleted}`",
                "- Changed files:",
            ]
        )
        if task.patch_result.changed_files:
            for item in task.patch_result.changed_files:
                lines.append(f"  - `{item}`")
        else:
            lines.append("  - None")
        if task.patch_result.error:
            lines.append(f"- Patch error: {task.patch_result.error}")
    else:
        lines.append("- No patch applied.")

    lines.extend(["", "## Test Result", ""])
    if task.test_result:
        result = "PASS" if task.test_result.passed else "FAIL"
        lines.extend(
            [
                f"- Result: `{result}`",
                f"- Command: `{task.test_result.command}`",
                f"- Exit code: `{task.test_result.exit_code}`",
                f"- Log: `{task.test_result.log_path}`",
                f"- Policy: `{task.test_result.policy_path or 'n/a'}`",
                f"- Timed out: `{task.test_result.timed_out}`",
                f"- Log truncated: `{task.test_result.log_truncated}`",
            ]
        )
    else:
        lines.append("- Tests not run.")
    if task.pr_body_path:
        lines.extend(["", "## PR Draft", "", f"- PR body: `{task.pr_body_path}`"])
    if task.pr_handoff_path:
        lines.extend(
            [
                "",
                "## PR Handoff",
                "",
                f"- Handoff: `{task.pr_handoff_path}`",
                f"- Draft PR script: `{task.pr_create_script_path or 'n/a'}`",
            ]
        )
    if task.error:
        lines.extend(["", "## Error", "", f"- Code: `{task.error_code or 'TASK_FAILED'}`", f"- Detail: {task.error}"])
    lines.append("")
    return "\n".join(lines)

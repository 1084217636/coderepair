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
        "",
        "## Retrieved Context",
        "",
    ]
    if task.contexts:
        for ctx in task.contexts:
            lines.append(f"- `{ctx.path}` score={ctx.score} ({ctx.reason})")
    else:
        lines.append("- No context retrieved.")
    lines.extend(["", "## Test Result", ""])
    if task.test_result:
        result = "PASS" if task.test_result.passed else "FAIL"
        lines.extend(
            [
                f"- Result: `{result}`",
                f"- Command: `{task.test_result.command}`",
                f"- Exit code: `{task.test_result.exit_code}`",
                f"- Log: `{task.test_result.log_path}`",
            ]
        )
    else:
        lines.append("- Tests not run.")
    if task.error:
        lines.extend(["", "## Error", "", task.error])
    lines.append("")
    return "\n".join(lines)

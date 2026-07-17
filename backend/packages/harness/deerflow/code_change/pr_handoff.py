from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path

from deerflow.code_change.models import PatchResult, Project, Task, TestResult


@dataclass(slots=True)
class PRHandoff:
    handoff_path: str
    script_path: str
    branch_name: str


def write_pr_handoff(project: Project, task: Task, patch: PatchResult, test_result: TestResult, artifact_dir: str | Path) -> PRHandoff:
    artifact_path = Path(artifact_dir)
    branch_name = "ai-code-change/" + task.task_id.replace("_", "-")
    title = build_title(task.requirement)
    commit_message = title
    body_path = Path(task.pr_body_path) if task.pr_body_path else artifact_path / "pr_body.md"
    patch_path = Path(patch.patch_path)

    data = {
        "task_id": task.task_id,
        "project_id": task.project_id,
        "repo_url": project.repo_url,
        "source_repo_path": project.repo_path,
        "base_branch": project.default_branch,
        "branch_name": branch_name,
        "title": title,
        "commit_message": commit_message,
        "body_path": str(body_path),
        "patch_path": str(patch_path),
        "changed_files": patch.changed_files,
        "lines_added": patch.lines_added,
        "lines_deleted": patch.lines_deleted,
        "test_result": {
            "command": test_result.command,
            "exit_code": test_result.exit_code,
            "duration_seconds": test_result.duration_seconds,
            "log_path": test_result.log_path,
        },
        "commands": build_commands(project, branch_name, commit_message, title, body_path, patch_path),
        "note": "Review and run these commands from source_repo_path only after human approval.",
    }

    handoff_path = artifact_path / "pr_handoff.json"
    handoff_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    script_path = artifact_path / "create_draft_pr.sh"
    script_path.write_text(render_script(data), encoding="utf-8")
    script_path.chmod(0o755)

    return PRHandoff(handoff_path=str(handoff_path), script_path=str(script_path), branch_name=branch_name)


def build_title(requirement: str) -> str:
    cleaned = " ".join(requirement.strip().split())
    if not cleaned:
        cleaned = "AI code change task"
    if len(cleaned) > 72:
        cleaned = cleaned[:69].rstrip() + "..."
    return cleaned


def build_commands(project: Project, branch_name: str, commit_message: str, title: str, body_path: Path, patch_path: Path) -> list[str]:
    commands = [
        f"git checkout {shlex.quote(project.default_branch)}",
        "git pull --ff-only",
        f"git checkout -b {shlex.quote(branch_name)}",
        f"git apply {shlex.quote(str(patch_path))}",
        "git add -A",
        f"git commit -m {shlex.quote(commit_message)}",
    ]
    if project.repo_url:
        commands.append(f"git push -u origin {shlex.quote(branch_name)}")
        commands.append(f"gh pr create --draft --base {shlex.quote(project.default_branch)} --head {shlex.quote(branch_name)} --title {shlex.quote(title)} --body-file {shlex.quote(str(body_path))}")
    else:
        commands.append("# repo_url is empty; configure origin before pushing and creating a draft PR.")
    return commands


def render_script(data: dict) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Generated PR handoff script. Review pr_handoff.json before running.",
        f"cd {shlex.quote(data['source_repo_path'])}",
        "",
    ]
    lines.extend(data["commands"])
    lines.append("")
    return "\n".join(lines)

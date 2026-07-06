from __future__ import annotations

import re
import subprocess
from pathlib import Path

from deerflow.code_change.models import PatchResult


class PatchRejected(ValueError):
    pass


def apply_patch_file(repo_path: str, patch_file: str | Path, artifact_dir: str | Path) -> PatchResult:
    patch_text = Path(patch_file).read_text(encoding="utf-8")
    return apply_patch_text(repo_path, patch_text, artifact_dir)


def apply_patch_text(repo_path: str, patch_text: str, artifact_dir: str | Path) -> PatchResult:
    root = Path(repo_path).resolve()
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    patch_path = artifacts / "patch.diff"
    check_log = artifacts / "patch_check.log"
    apply_log = artifacts / "patch_apply.log"
    patch_path.write_text(patch_text, encoding="utf-8")

    changed_files = extract_changed_files(patch_text)
    validate_patch_paths(changed_files)
    added, deleted = count_changed_lines(patch_text)

    result = PatchResult(
        patch_path=str(patch_path),
        changed_files=changed_files,
        lines_added=added,
        lines_deleted=deleted,
        check_log_path=str(check_log),
        apply_log_path=str(apply_log),
    )

    check = run_git_apply(root, patch_path, check=True)
    check_log.write_text(check.stdout, encoding="utf-8")
    if check.returncode != 0:
        result.error = check.stdout.strip() or "git apply --check failed"
        return result

    applied = run_git_apply(root, patch_path, check=False)
    apply_log.write_text(applied.stdout, encoding="utf-8")
    if applied.returncode != 0:
        result.error = applied.stdout.strip() or "git apply failed"
        return result

    result.applied = True
    return result


def extract_changed_files(patch_text: str) -> list[str]:
    paths: list[str] = []
    for line in patch_text.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            raw = line[4:].strip()
            if raw == "/dev/null":
                continue
            path = strip_diff_prefix(raw)
            if path and path not in paths:
                paths.append(path)
        elif line.startswith("diff --git "):
            match = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            if match:
                for raw in match.groups():
                    path = strip_diff_prefix(raw)
                    if path and path not in paths:
                        paths.append(path)
    return paths


def strip_diff_prefix(raw: str) -> str:
    raw = raw.split("\t", 1)[0].strip()
    if raw.startswith("a/") or raw.startswith("b/"):
        return raw[2:]
    return raw


def validate_patch_paths(paths: list[str]) -> None:
    if not paths:
        raise PatchRejected("patch does not contain changed file paths")
    for item in paths:
        path = Path(item)
        if path.is_absolute() or ".." in path.parts:
            raise PatchRejected(f"patch path escapes repository: {item}")


def count_changed_lines(patch_text: str) -> tuple[int, int]:
    added = 0
    deleted = 0
    for line in patch_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            deleted += 1
    return added, deleted


def run_git_apply(root: Path, patch_path: Path, check: bool) -> subprocess.CompletedProcess[str]:
    command = ["git", "apply"]
    if check:
        command.append("--check")
    command.append(str(patch_path))
    return subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def write_pr_body(task_id: str, requirement: str, result: PatchResult, test_passed: bool, artifact_dir: str | Path) -> Path:
    path = Path(artifact_dir) / "pr_body.md"
    test_result = "PASS" if test_passed else "FAIL"
    changed = "\n".join(f"- `{item}`" for item in result.changed_files) or "- No changed files detected."
    body = f"""# Code Change PR Draft

## Requirement

{requirement}

## Task

- Task ID: `{task_id}`

## Changed Files

{changed}

## Core Changes

- Applied a reviewed patch artifact in an isolated repository workspace.
- Patch stats: `{result.lines_added}` additions, `{result.lines_deleted}` deletions.

## Test Result

- Result: `{test_result}`

## Risks

- Patch is generated from local artifacts in V2; human review is still required before merging.
- The current workflow validates tests but does not yet open a real GitHub PR automatically.

## Rollback

- Revert the generated patch or reset the task branch before merge.
"""
    path.write_text(body, encoding="utf-8")
    return path

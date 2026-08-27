#!/usr/bin/env python3
"""Validate the learning contract for the CodeRepair handbook."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


REPO_ROOT = Path(__file__).resolve().parents[1]
HANDBOOK_DIR = REPO_ROOT / "docs" / "handbook"
MOBILE_DIR = REPO_ROOT / "docs" / "mobile_ai_interview"
NUMBERED_CHAPTER = re.compile(r"^\d{2}_.+\.md$")
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")

READING_HEADER = "## 本章代码阅读任务"
SELF_TEST_HEADER = "## 本章自测"
ANSWER_HEADER = "## 参考答案"
MOBILE_ANSWER_SECTIONS = (
    "### 面试官问",
    "### 30 秒回答",
    "### 详细回答",
    "### 结合当前 CodeRepair 源码",
    "### 技术选型与替代",
    "### 边界与追问",
)


def validate_learning_contract(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    positions: list[int] = []
    for header in (READING_HEADER, SELF_TEST_HEADER, ANSWER_HEADER):
        position = text.find(header)
        if position < 0:
            errors.append(f"{path.relative_to(REPO_ROOT)}: 缺少 `{header}`")
        positions.append(position)

    if all(position >= 0 for position in positions) and positions != sorted(positions):
        errors.append(
            f"{path.relative_to(REPO_ROOT)}: 阅读任务、自测和参考答案的顺序不正确"
        )

    if positions[0] >= 0:
        block_end = positions[1] if positions[1] >= 0 else len(text)
        reading_block = text[positions[0] : block_end]
        code_refs = re.findall(r"`([^`]+)`", reading_block)
        has_concrete_ref = any(
            "/" in ref or ref.endswith(".py") or ref.endswith(".tsx")
            for ref in code_refs
        )
        if not has_concrete_ref:
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: 阅读任务没有写明具体代码文件"
            )

        required_labels = ("阅读顺序", "看到什么程度", "暂不要求", "验收动作")
        for label in required_labels:
            if label not in reading_block:
                errors.append(
                    f"{path.relative_to(REPO_ROOT)}: 阅读任务缺少“{label}”说明"
                )

        if "> 我" not in reading_block or "带答案" not in reading_block:
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: 阅读任务缺少可复制的单问题 AI 提问，"
                "或没有要求在回答中附带答案"
            )

    if positions[1] >= 0 and positions[2] >= 0:
        questions = re.findall(r"^\d+\.\s+", text[positions[1] : positions[2]], re.M)
        answers = re.findall(r"^\d+\.\s+", text[positions[2] :], re.M)
        if not questions:
            errors.append(f"{path.relative_to(REPO_ROOT)}: 自测部分没有编号题目")
        elif len(answers) < len(questions):
            errors.append(f"{path.relative_to(REPO_ROOT)}: 参考答案少于自测题目")

    return errors


def validate_mobile_contract(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(REPO_ROOT)
    errors: list[str] = []
    question_count = len(re.findall(r"^## 问题 \d+：", text, re.M))
    if question_count < 3:
        errors.append(f"{relative}: 至少需要 3 道可直接背诵的面试题")
    for header in MOBILE_ANSWER_SECTIONS:
        actual = len(re.findall(rf"^{re.escape(header)}$", text, re.M))
        if actual != question_count:
            errors.append(
                f"{relative}: `{header}` 数量为 {actual}，应与问题数量 {question_count} 一致"
            )
    for unfinished in ("待补充", "再去问 AI", "继续向 AI 提问"):
        if unfinished in text:
            errors.append(f"{relative}: 包含未完成学习指令 `{unfinished}`")
    return errors


def validate_local_links(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    for raw_target in MARKDOWN_LINK.findall(text):
        target = raw_target.strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue

        target_without_title = target.split(maxsplit=1)[0].strip("<>")
        relative_target = unquote(target_without_title.split("#", 1)[0])
        if not relative_target:
            continue

        resolved = (path.parent / relative_target).resolve()
        try:
            resolved.relative_to(REPO_ROOT)
        except ValueError:
            errors.append(f"{path.relative_to(REPO_ROOT)}: 链接越出仓库 `{raw_target}`")
            continue

        if not resolved.exists():
            errors.append(
                f"{path.relative_to(REPO_ROOT)}: 本地链接不存在 `{raw_target}`"
            )

    return errors


def main() -> int:
    if not HANDBOOK_DIR.is_dir():
        print("FAIL: docs/handbook 不存在", file=sys.stderr)
        return 1

    chapters = sorted(
        path for path in HANDBOOK_DIR.iterdir() if NUMBERED_CHAPTER.match(path.name)
    )
    expected_names = {
        "00_START_HERE.md",
        "01_PROJECT_BOUNDARY.md",
        "02_FIRST_DEMO.md",
        "03_PYTHON_ASYNC_HTTP.md",
        "04_LLM_FOUNDATIONS.md",
        "05_DEERFLOW_ARCHITECTURE.md",
        "06_AGENT_LOOP_LANGGRAPH.md",
        "07_TOOL_CALLING.md",
        "08_MIDDLEWARE_CONTEXT.md",
        "09_MEMORY_SKILLS_SUBAGENTS.md",
        "10_REPOSITORY_RETRIEVAL.md",
        "11_CODING_AGENT.md",
        "12_WORKSPACE_PATCH_TEST.md",
        "13_ANCHORED_BRANCH.md",
        "14_BRANCH_CONTEXT.md",
        "15_DECISION_CONTROL_PLANE.md",
        "16_SECURITY_GUARDRAILS.md",
        "17_EVALUATION_OBSERVABILITY.md",
        "18_FAILURE_DEBUGGING.md",
        "19_END_TO_END_CODE_MAP.md",
        "20_RESUME_STUDY_PLAN.md",
        "21_AI_ASSISTED_AGENT_DEVELOPMENT.md",
    }

    actual_names = {path.name for path in chapters}
    errors = [
        f"docs/handbook: 缺少章节 `{name}`"
        for name in sorted(expected_names - actual_names)
    ]
    errors.extend(
        f"docs/handbook: 未登记的编号章节 `{name}`"
        for name in sorted(actual_names - expected_names)
    )

    for path in chapters:
        errors.extend(validate_learning_contract(path))

    expected_mobile_names = {
        "01_GO_BACKEND_TO_AI.md",
        "02_LLM_AGENT_DEERFLOW.md",
        "03_CONTROL_PLANE_TASK_API.md",
        "04_PATCH_AGENT_RETRIEVAL.md",
        "05_WORKSPACE_PATCH_TEST.md",
        "06_STATE_QUEUE_HITL.md",
        "07_ANCHORED_BRANCH_CONTEXT.md",
        "08_SECURITY_EVALUATION_FAILURE.md",
        "09_PROJECT_INTERVIEW.md",
    }
    mobile_chapters = (
        sorted(
            path for path in MOBILE_DIR.iterdir() if NUMBERED_CHAPTER.match(path.name)
        )
        if MOBILE_DIR.is_dir()
        else []
    )
    actual_mobile_names = {path.name for path in mobile_chapters}
    errors.extend(
        f"docs/mobile_ai_interview: 缺少章节 `{name}`"
        for name in sorted(expected_mobile_names - actual_mobile_names)
    )
    errors.extend(
        f"docs/mobile_ai_interview: 未登记的编号章节 `{name}`"
        for name in sorted(actual_mobile_names - expected_mobile_names)
    )
    for path in mobile_chapters:
        errors.extend(validate_mobile_contract(path))

    for path in [
        HANDBOOK_DIR / "README.md",
        MOBILE_DIR / "README.md",
        REPO_ROOT / "docs" / "README.md",
        REPO_ROOT / "docs" / "README_STUDY.md",
        *chapters,
        *mobile_chapters,
    ]:
        if path.exists():
            errors.extend(validate_local_links(path))

    if errors:
        print("CodeRepair handbook validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"PASS CodeRepair handbook: {len(chapters)} chapters have exact reading tasks, "
        f"same-file answers; {len(mobile_chapters)} mobile chapters have complete interview answers; "
        "all checked local links are valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

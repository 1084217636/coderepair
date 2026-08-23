"""DeerFlow-native Agent that proposes, but never applies, a code patch.

The control-plane boundary is deliberate: the model may search and read the
registered repository, then submit one unified diff through a typed tool.  It
cannot write files or execute commands.  The existing deterministic worker is
the only component allowed to validate, apply and test the submitted patch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, tool

from deerflow.agents.factory import create_deerflow_agent
from deerflow.code_change.context_retriever import retrieve_context
from deerflow.code_change.patcher import extract_changed_files, validate_patch_paths
from deerflow.code_change.repo_scanner import scan_repo

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

MAX_READ_CHARS = 24_000
MAX_PATCH_BYTES = 256_000

SYSTEM_PROMPT = """You are the patch-proposal stage of a controlled code-change platform.

Your job is narrow:
1. Use code_change_search to locate relevant files.
2. Use code_change_read_file to inspect exact source when needed.
3. Call code_change_submit_patch exactly once with a unified diff and a short rationale.

Never claim that a patch was applied, tested, committed, pushed or merged.  This
Agent can only propose a candidate.  A deterministic worker validates paths,
applies the diff in an isolated workspace, runs a server-approved test profile,
and waits for human approval.
"""


@dataclass(slots=True)
class AgentPatchResult:
    patch_text: str
    rationale: str
    changed_files: list[str]
    final_message: str
    thread_id: str
    run_id: str


@dataclass(slots=True)
class PatchCapture:
    patch_text: str = ""
    rationale: str = ""
    changed_files: list[str] | None = None


def _safe_repo_file(repo_root: Path, relative_path: str) -> Path:
    requested = Path(relative_path)
    if requested.is_absolute() or ".." in requested.parts:
        raise ValueError("file path must stay inside the registered repository")
    resolved = (repo_root / requested).resolve()
    if not resolved.is_relative_to(repo_root):
        raise ValueError("file path escapes the registered repository")
    if not resolved.is_file():
        raise ValueError(f"source file does not exist: {relative_path}")
    return resolved


def build_code_change_tools(
    repo_path: str,
    requirement: str,
    capture: PatchCapture | None = None,
) -> tuple[list[BaseTool], PatchCapture]:
    """Build request-scoped read-only tools and one candidate submission tool."""

    root = Path(repo_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"repository does not exist: {repo_path}")
    files = scan_repo(str(root))
    indexed_paths = {Path(item.path).as_posix() for item in files}
    sink = capture or PatchCapture()

    @tool("code_change_search", parse_docstring=True)
    def code_change_search(query: str) -> str:
        """Search source files relevant to the requested change.

        Args:
            query: Keywords or a short description of the code to locate.
        """

        contexts = retrieve_context(str(root), query or requirement, files, limit=8)
        return json.dumps([context.to_dict() for context in contexts], ensure_ascii=False)

    @tool("code_change_read_file", parse_docstring=True)
    def code_change_read_file(path: str, start_line: int = 1, end_line: int = 240) -> str:
        """Read a bounded line range from one repository file.

        Args:
            path: Repository-relative source path returned by code_change_search.
            start_line: One-based first line, at least 1.
            end_line: Inclusive final line, no more than 400 lines after start.
        """

        if start_line < 1 or end_line < start_line:
            raise ValueError("invalid line range")
        end_line = min(end_line, start_line + 399)
        source = _safe_repo_file(root, path)
        indexed_path = source.relative_to(root).as_posix()
        if indexed_path not in indexed_paths:
            raise ValueError(f"source file is outside the indexed code set: {path}")
        lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = "\n".join(lines[start_line - 1 : end_line])
        return selected[:MAX_READ_CHARS]

    @tool("code_change_submit_patch", parse_docstring=True)
    def code_change_submit_patch(patch_text: str, rationale: str) -> str:
        """Submit one candidate unified diff to the deterministic worker.

        Args:
            patch_text: Complete unified diff with repository-relative paths.
            rationale: Short explanation of why the candidate satisfies the requirement.
        """

        if sink.patch_text:
            raise ValueError("a candidate patch has already been submitted")
        if not patch_text.strip():
            raise ValueError("candidate patch is empty")
        if len(patch_text.encode("utf-8")) > MAX_PATCH_BYTES:
            raise ValueError(f"candidate patch exceeds {MAX_PATCH_BYTES} bytes")
        changed_files = extract_changed_files(patch_text)
        validate_patch_paths(changed_files)
        if any(Path(path).parts and Path(path).parts[0] == ".git" for path in changed_files):
            raise ValueError("patch may not change Git metadata")
        sink.patch_text = patch_text
        sink.rationale = rationale.strip()[:2000]
        sink.changed_files = changed_files
        return json.dumps({"accepted": True, "changed_files": changed_files}, ensure_ascii=False)

    return [code_change_search, code_change_read_file, code_change_submit_patch], sink


def create_code_change_agent(
    model: BaseChatModel,
    repo_path: str,
    requirement: str,
    capture: PatchCapture | None = None,
) -> tuple[Any, PatchCapture]:
    """Create a minimal DeerFlow Agent with no shell or write-file tools."""

    tools, sink = build_code_change_tools(repo_path, requirement, capture)
    graph = create_deerflow_agent(
        model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[],
        name="code-change-patch-agent",
    )
    return graph, sink


def generate_patch_with_agent(
    model: BaseChatModel,
    repo_path: str,
    requirement: str,
    *,
    thread_id: str,
    run_id: str,
    task_id: str = "",
) -> AgentPatchResult:
    """Run the Agent and return the tool-submitted candidate patch.

    A missing ``code_change_submit_patch`` call is a hard failure.  We do not
    scrape arbitrary prose or Markdown fences because that would bypass the
    typed submission and validation boundary.
    """

    graph, sink = create_code_change_agent(model, repo_path, requirement)
    result = graph.invoke(
        {"messages": [HumanMessage(content=(f"Requirement:\n{requirement}\n\nInspect the registered repository and submit one candidate unified diff."))]},
        config={
            "configurable": {"thread_id": thread_id},
            "metadata": {
                "code_change_task_id": task_id,
                "code_change_thread_id": thread_id,
                "code_change_run_id": run_id,
            },
        },
    )
    if not sink.patch_text:
        raise ValueError("Agent finished without calling code_change_submit_patch")
    messages = result.get("messages", []) if isinstance(result, dict) else []
    final_message = ""
    if messages:
        content = getattr(messages[-1], "content", "")
        final_message = content if isinstance(content, str) else str(content)
    return AgentPatchResult(
        patch_text=sink.patch_text,
        rationale=sink.rationale,
        changed_files=sink.changed_files or [],
        final_message=final_message,
        thread_id=thread_id,
        run_id=run_id,
    )

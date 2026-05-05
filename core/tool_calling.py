"""
Lightweight tool-calling runtime metadata.

The platform still owns execution; LLM output is never allowed to directly
touch the filesystem. This module gives each execution capability a stable
schema, permission scope, and audit record so a run can be inspected as a
bounded tool workflow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import time
from typing import Any, Callable, Dict, Iterable, List, Optional


def _json_safe(value: Any) -> Any:
    """Convert common runtime values into JSON-serializable structures."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class ToolSpec:
    """A declared execution capability exposed to the workflow."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    permission_scope: str
    retry_policy: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "permission_scope": self.permission_scope,
            "retry_policy": self.retry_policy,
        }


@dataclass
class ToolCallRecord:
    """One tool execution record."""

    sequence: int
    name: str
    status: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    started_at: str
    finished_at: str
    duration_ms: int
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "name": self.name,
            "status": self.status,
            "input": _json_safe(self.input),
            "output": _json_safe(self.output),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


DEFAULT_TOOL_SPECS: List[ToolSpec] = [
    ToolSpec(
        name="repository_scan",
        description="Scan files inside the target workspace after path filtering.",
        input_schema={"type": "object", "required": ["workspace_root"]},
        output_schema={"type": "object", "properties": {"total_files": {"type": "integer"}}},
        permission_scope="read_workspace",
    ),
    ToolSpec(
        name="go_ast_analyze",
        description="Extract Go package, import, function, method, and call relation metadata.",
        input_schema={"type": "object", "required": ["language"]},
        output_schema={"type": "object", "properties": {"analyzed_files": {"type": "integer"}}},
        permission_scope="read_workspace",
    ),
    ToolSpec(
        name="context_retrieve",
        description="Retrieve code, document, and engineering context for the user task.",
        input_schema={"type": "object", "required": ["query"]},
        output_schema={"type": "object", "properties": {"retrieved_chunks": {"type": "integer"}}},
        permission_scope="read_workspace",
    ),
    ToolSpec(
        name="llm_generate",
        description="Call the selected LLM provider with the assembled context.",
        input_schema={"type": "object", "required": ["mode"]},
        output_schema={"type": "object", "properties": {"response_chars": {"type": "integer"}}},
        permission_scope="external_llm",
        retry_policy={"max_attempts": 1},
    ),
    ToolSpec(
        name="code_extract",
        description="Extract language-specific fenced code blocks from the model response.",
        input_schema={"type": "object", "required": ["language"]},
        output_schema={"type": "object", "properties": {"code_block_count": {"type": "integer"}}},
        permission_scope="memory_only",
    ),
    ToolSpec(
        name="patch_apply",
        description="Apply one explicit file write after workspace boundary checks.",
        input_schema={"type": "object", "required": ["file"]},
        output_schema={"type": "object", "properties": {"status": {"type": "string"}}},
        permission_scope="write_workspace_single_file",
    ),
    ToolSpec(
        name="validate",
        description="Run local or Docker validation commands and capture stdout/stderr.",
        input_schema={"type": "object", "required": ["validation_mode"]},
        output_schema={"type": "object", "properties": {"success": {"type": "boolean"}}},
        permission_scope="execute_validation_command",
    ),
    ToolSpec(
        name="config_check",
        description="Check JSON/YAML/CSV config files for missing fields, duplicate ids, broken references, and type drift.",
        input_schema={"type": "object", "required": ["file"]},
        output_schema={"type": "object", "properties": {"passed": {"type": "boolean"}}},
        permission_scope="read_workspace",
    ),
    ToolSpec(
        name="test_suggest",
        description="Inspect Go functions and existing tests to suggest missing unit tests and edge cases.",
        input_schema={"type": "object", "required": ["workspace_root"]},
        output_schema={"type": "object", "properties": {"missing_test_count": {"type": "integer"}}},
        permission_scope="read_workspace",
    ),
    ToolSpec(
        name="rollback",
        description="Restore a file from the backup created before patch application.",
        input_schema={"type": "object", "required": ["file"]},
        output_schema={"type": "object", "properties": {"status": {"type": "string"}}},
        permission_scope="restore_workspace_backup",
    ),
    ToolSpec(
        name="report",
        description="Write delivery artifacts for audit and handoff.",
        input_schema={"type": "object", "required": ["session_id"]},
        output_schema={"type": "object", "properties": {"artifacts": {"type": "array"}}},
        permission_scope="write_artifacts",
    ),
]


class ToolLedger:
    """Registry plus append-only audit log for workflow tool calls."""

    def __init__(
        self,
        workspace_root: Path,
        specs: Optional[Iterable[ToolSpec]] = None,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.specs: Dict[str, ToolSpec] = {}
        self.calls: List[ToolCallRecord] = []
        for spec in specs or DEFAULT_TOOL_SPECS:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        self.specs[spec.name] = spec

    def assert_registered(self, name: str) -> ToolSpec:
        if name not in self.specs:
            raise KeyError(f"unknown tool: {name}")
        return self.specs[name]

    def normalize_workspace_path(self, path_value: str | Path) -> str:
        """Return a workspace-relative path or raise when it escapes the workspace."""
        path = Path(path_value)
        candidate = path if path.is_absolute() else self.workspace_root / path
        resolved = candidate.resolve(strict=False)
        try:
            relative_path = resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise PermissionError(f"path is outside workspace: {path_value}") from exc
        return str(relative_path)

    def record(
        self,
        name: str,
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None,
        *,
        status: str = "success",
        error: Optional[str] = None,
        started_at: Optional[float] = None,
    ) -> ToolCallRecord:
        self.assert_registered(name)
        finished = time.time()
        started = started_at if started_at is not None else finished
        record = ToolCallRecord(
            sequence=len(self.calls) + 1,
            name=name,
            status=status,
            input=_json_safe(input_payload or {}),
            output=_json_safe(output_payload or {}),
            started_at=datetime.fromtimestamp(started).isoformat(),
            finished_at=datetime.fromtimestamp(finished).isoformat(),
            duration_ms=max(0, int((finished - started) * 1000)),
            error=error,
        )
        self.calls.append(record)
        return record

    def invoke(
        self,
        name: str,
        input_payload: Dict[str, Any],
        fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run a function and record success/failure as a tool call."""
        self.assert_registered(name)
        started = time.time()
        try:
            output = fn()
        except Exception as exc:
            self.record(
                name,
                input_payload,
                {},
                status="error",
                error=str(exc),
                started_at=started,
            )
            raise
        self.record(name, input_payload, output, started_at=started)
        return output

    def to_schema_document(self) -> Dict[str, Any]:
        return {
            "schema_version": "v1",
            "workspace_root": str(self.workspace_root),
            "tools": [spec.to_dict() for spec in self.specs.values()],
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "v1",
            "workspace_root": str(self.workspace_root),
            "tool_count": len(self.specs),
            "call_count": len(self.calls),
            "calls": [call.to_dict() for call in self.calls],
        }

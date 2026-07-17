from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    RETRIEVING_CONTEXT = "RETRIEVING_CONTEXT"
    PATCH_RECEIVED = "PATCH_RECEIVED"
    VALIDATING_PATCH = "VALIDATING_PATCH"
    GENERATING_PATCH = "GENERATING_PATCH"
    APPLYING_PATCH = "APPLYING_PATCH"
    RUNNING_TESTS = "RUNNING_TESTS"
    REVIEWING = "REVIEWING"
    HANDOFF_READY = "HANDOFF_READY"
    PR_CREATED = "PR_CREATED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(slots=True)
class Project:
    project_id: str
    name: str
    repo_path: str
    test_command: str
    owner_id: str = "default"
    repo_url: str = ""
    default_branch: str = "main"
    tech_stack: list[str] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        return cls(**data)


@dataclass(slots=True)
class TaskStep:
    name: str
    status: str
    summary: str = ""
    error: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CodeFile:
    path: str
    language: str
    size: int
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RetrievedContext:
    path: str
    score: int
    reason: str
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TestResult:
    command: str
    exit_code: int
    duration_seconds: float
    log_path: str
    timed_out: bool = False
    log_truncated: bool = False
    policy_path: str = ""

    @property
    def passed(self) -> bool:
        return self.exit_code == 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PatchResult:
    patch_path: str
    changed_files: list[str] = field(default_factory=list)
    lines_added: int = 0
    lines_deleted: int = 0
    applied: bool = False
    check_log_path: str = ""
    apply_log_path: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Task:
    task_id: str
    project_id: str
    requirement: str
    owner_id: str = "default"
    status: TaskStatus = TaskStatus.CREATED
    steps: list[TaskStep] = field(default_factory=list)
    contexts: list[RetrievedContext] = field(default_factory=list)
    patch_result: PatchResult | None = None
    test_result: TestResult | None = None
    pr_body_path: str = ""
    pr_handoff_path: str = ""
    pr_create_script_path: str = ""
    artifact_dir: str = ""
    source_repo_path: str = ""
    workspace_path: str = ""
    workspace_manifest_path: str = ""
    sandbox_kind: str = ""
    created_at: str = ""
    updated_at: str = ""
    error: str = ""
    attempt_count: int = 0
    max_attempts: int = 2
    last_error: str = ""
    queued_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    worker_id: str = ""
    lease_expires_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = str(self.status)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        data = dict(data)
        data["status"] = TaskStatus(data["status"])
        data["steps"] = [TaskStep(**item) for item in data.get("steps", [])]
        data["contexts"] = [RetrievedContext(**item) for item in data.get("contexts", [])]
        if data.get("patch_result"):
            data["patch_result"] = PatchResult(**data["patch_result"])
        if data.get("test_result"):
            data["test_result"] = TestResult(**data["test_result"])
        return cls(**data)


def project_safe_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in name.strip())
    return safe.strip("-_") or "project"


def ensure_repo_path(path: str, allowed_roots: list[Path] | None = None) -> str:
    repo = Path(path).expanduser().resolve()
    if not repo.exists() or not repo.is_dir():
        raise ValueError(f"repo_path does not exist or is not a directory: {path}")
    if allowed_roots and not any(repo == root or repo.is_relative_to(root) for root in allowed_roots):
        roots = ", ".join(str(root) for root in allowed_roots)
        raise ValueError(f"repo_path is outside allowed repository roots: {roots}")
    return str(repo)

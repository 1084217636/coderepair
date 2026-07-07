from __future__ import annotations

import json
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path


SHELL_OPERATORS = {"&&", "||", ";", "|", ">", ">>", "<", "$(", "`"}


@dataclass(slots=True)
class SandboxPolicy:
    sandbox_kind: str = "local-copy"
    allowed_executables: list[str] = field(
        default_factory=lambda: ["python", "python3", "pytest", "go", "npm", "pnpm", "yarn", "mvn", "gradle"]
    )
    timeout_seconds: int = 120
    max_log_bytes: int = 64_000
    network_disabled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class SandboxPolicyViolation(ValueError):
    pass


def default_policy() -> SandboxPolicy:
    return SandboxPolicy()


def write_policy(policy: SandboxPolicy, artifact_dir: str | Path) -> Path:
    path = Path(artifact_dir) / "sandbox_policy.json"
    path.write_text(json.dumps(policy.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def build_command(command: str, policy: SandboxPolicy) -> list[str]:
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise SandboxPolicyViolation(f"invalid test command: {exc}") from exc
    if not parts:
        raise SandboxPolicyViolation("empty test command")
    for part in parts:
        if part in SHELL_OPERATORS:
            raise SandboxPolicyViolation(f"shell operator is not allowed: {part}")
    executable = Path(parts[0]).name
    if executable not in set(policy.allowed_executables):
        raise SandboxPolicyViolation(f"executable is not allowed: {executable}")
    return parts

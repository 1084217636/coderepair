from __future__ import annotations

import json
import os
import shlex

TEST_PROFILES_ENV_VAR = "DEER_FLOW_CODE_CHANGE_TEST_PROFILES"

DEFAULT_TEST_PROFILES: dict[str, list[str]] = {
    "python-pytest": ["python3", "-m", "pytest", "-q"],
    "go-test": ["go", "test", "./..."],
    "frontend-check": ["pnpm", "check"],
}


def load_test_profiles() -> dict[str, str]:
    raw = os.getenv(TEST_PROFILES_ENV_VAR, "").strip()
    configured = DEFAULT_TEST_PROFILES if not raw else _parse_profiles(raw)
    return {name: shlex.join(args) for name, args in configured.items()}


def _parse_profiles(raw: str) -> dict[str, list[str]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{TEST_PROFILES_ENV_VAR} must be valid JSON") from exc
    if not isinstance(data, dict) or not data:
        raise ValueError(f"{TEST_PROFILES_ENV_VAR} must be a non-empty JSON object")
    profiles: dict[str, list[str]] = {}
    for name, args in data.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("test profile names must be non-empty strings")
        if not isinstance(args, list) or not args or not all(isinstance(arg, str) and arg for arg in args):
            raise ValueError(f"test profile {name!r} must be a non-empty JSON string array")
        profiles[name.strip()] = args
    return profiles

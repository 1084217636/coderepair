"""Narrow authentication helpers for the Code Change worker endpoint."""

from __future__ import annotations

import os
import secrets
from typing import Any

CODE_CHANGE_WORKER_PATH = "/api/code-change/worker/run-once"
CODE_CHANGE_WORKER_TOKEN_ENV_VAR = "DEER_FLOW_CODE_CHANGE_WORKER_TOKEN"
CODE_CHANGE_WORKER_TOKEN_HEADER_NAME = "X-Code-Change-Worker-Token"


def is_code_change_worker_request(request: Any) -> bool:
    if request.url.path.rstrip("/") != CODE_CHANGE_WORKER_PATH:
        return False
    expected = os.getenv(CODE_CHANGE_WORKER_TOKEN_ENV_VAR, "").strip()
    provided = request.headers.get(CODE_CHANGE_WORKER_TOKEN_HEADER_NAME, "")
    return bool(expected and provided) and secrets.compare_digest(provided, expected)

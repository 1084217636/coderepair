from pathlib import Path

import pytest

from core.tool_calling import ToolLedger


def test_tool_ledger_records_registered_calls(tmp_path):
    ledger = ToolLedger(tmp_path)

    ledger.record(
        "repository_scan",
        {"workspace_root": str(tmp_path)},
        {"total_files": 2},
    )

    payload = ledger.to_dict()

    assert payload["call_count"] == 1
    assert payload["calls"][0]["name"] == "repository_scan"
    assert payload["calls"][0]["output"]["total_files"] == 2


def test_tool_ledger_rejects_paths_outside_workspace(tmp_path):
    ledger = ToolLedger(tmp_path)

    with pytest.raises(PermissionError):
        ledger.normalize_workspace_path(Path("..") / "outside.go")


def test_tool_ledger_normalizes_workspace_relative_paths(tmp_path):
    target = tmp_path / "pkg" / "service.go"
    ledger = ToolLedger(tmp_path)

    assert ledger.normalize_workspace_path(target) == "pkg/service.go"

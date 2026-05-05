"""
Go test suggestion helper.

This is a deterministic companion to the Agent workflow: it inspects Go
functions and existing tests, then emits missing test targets and edge-case
prompts that an LLM or developer can turn into concrete unit tests.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from analyzers.go_ast import GoAnalyzer


class GoTestSuggester:
    """Generate test completion suggestions for a Go repository."""

    def __init__(self, workspace_root: str | Path):
        self.workspace_root = Path(workspace_root)
        self.analyzer = GoAnalyzer(self.workspace_root)

    def suggest(self) -> Dict[str, Any]:
        source_files = sorted(
            path for path in self.workspace_root.rglob("*.go")
            if not path.name.endswith("_test.go")
        )
        test_files = sorted(self.workspace_root.rglob("*_test.go"))

        functions = []
        for file_path in source_files:
            analysis = self.analyzer.analyze_file(file_path)
            for function in analysis.get("functions", []):
                if function == "main" or function.startswith("init"):
                    continue
                functions.append(
                    {
                        "name": function,
                        "file": str(file_path.relative_to(self.workspace_root)),
                        "suggested_test": f"Test{function}",
                    }
                )

        existing_tests = self._collect_existing_tests(test_files)
        suggestions = []
        for function in functions:
            has_test = function["suggested_test"] in existing_tests
            suggestion = {
                **function,
                "has_existing_test": has_test,
                "priority": "medium" if has_test else "high",
                "edge_cases": self._edge_cases_for_function(function["name"]),
            }
            suggestions.append(suggestion)

        missing = [item for item in suggestions if not item["has_existing_test"]]
        return {
            "workspace": str(self.workspace_root),
            "source_files": len(source_files),
            "test_files": len(test_files),
            "function_count": len(functions),
            "existing_test_count": len(existing_tests),
            "missing_test_count": len(missing),
            "suggestions": suggestions,
        }

    @staticmethod
    def _collect_existing_tests(test_files: List[Path]) -> set[str]:
        tests: set[str] = set()
        pattern = re.compile(r"^func\s+(Test[A-Za-z0-9_]+)\s*\(", re.MULTILINE)
        for file_path in test_files:
            try:
                tests.update(pattern.findall(file_path.read_text(encoding="utf-8")))
            except OSError:
                continue
        return tests

    @staticmethod
    def _edge_cases_for_function(function_name: str) -> List[str]:
        lowered = function_name.lower()
        cases = ["normal input", "zero value input"]
        if any(token in lowered for token in ("calculate", "count", "sum", "score", "price")):
            cases.extend(["negative number", "large number", "boundary value"])
        if any(token in lowered for token in ("parse", "decode", "load", "read")):
            cases.extend(["empty input", "malformed input"])
        if any(token in lowered for token in ("validate", "check", "verify")):
            cases.extend(["missing required field", "invalid enum/value"])
        if any(token in lowered for token in ("get", "find", "query")):
            cases.extend(["not found", "duplicate record"])
        return list(dict.fromkeys(cases))

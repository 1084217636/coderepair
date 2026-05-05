"""
Expanded Go task catalog for repeatable engineering evaluation.
"""
from __future__ import annotations

from typing import List

from config import settings
from .metrics import BenchmarkCase


SAMPLE_GO_WORKSPACE = str(settings.PLATFORM_ROOT / "examples/sample_go_project")


_GO_REPAIR_CASE_SPECS = [
    (
        "compile_import_missing",
        "Find where a missing import would break the Go build and propose a minimal fix. Do not write files.",
        "compile_error",
        ["main.go", "go.mod"],
        ["import", "build", "main"],
    ),
    (
        "compile_signature_mismatch",
        "Explain how to repair a function signature mismatch around Calculate and its callers. Do not write files.",
        "compile_error",
        ["main.go", "main_test.go"],
        ["calculate", "signature", "test"],
    ),
    (
        "compile_field_rename",
        "Plan a safe field rename in a Go struct and identify which files must be checked. Do not write files.",
        "compile_error",
        ["main.go", "main_test.go"],
        ["rename", "field", "test"],
    ),
    (
        "compile_package_boundary",
        "Review package and module boundaries for changes that could cause build failures. Do not write files.",
        "compile_error",
        ["main.go", "go.mod"],
        ["package", "module", "build"],
    ),
    (
        "compile_return_type",
        "Describe how to fix a wrong return type in Calculate while keeping tests aligned. Do not write files.",
        "compile_error",
        ["main.go", "main_test.go"],
        ["return", "calculate", "test"],
    ),
    (
        "unit_test_assertion_update",
        "Locate the unit test expectations for Calculate and propose the smallest assertion update. Do not write files.",
        "unit_test",
        ["main_test.go", "main.go"],
        ["assert", "calculate", "expected"],
    ),
    (
        "unit_test_table_case",
        "Suggest table-driven test cases that would catch the current Calculate bug. Do not write files.",
        "unit_test",
        ["main_test.go", "main.go"],
        ["test", "case", "calculate"],
    ),
    (
        "unit_test_edge_case",
        "Identify missing edge cases for Calculate and explain expected outcomes. Do not write files.",
        "unit_test",
        ["main_test.go", "main.go"],
        ["edge", "expected", "calculate"],
    ),
    (
        "unit_test_mock_boundary",
        "Explain where mock boundaries would belong if Calculate depended on an external service. Do not write files.",
        "unit_test",
        ["main.go", "main_test.go"],
        ["mock", "boundary", "test"],
    ),
    (
        "unit_test_failure_feedback",
        "Given a failing Calculate test, describe how validation logs should feed a second repair round. Do not write files.",
        "unit_test",
        ["main_test.go", "main.go"],
        ["validation", "repair", "test"],
    ),
    (
        "api_request_field_add",
        "Plan how to add a request field to a small Go API handler while limiting the change scope. Do not write files.",
        "api_change",
        ["main.go", "README.md"],
        ["request", "field", "scope"],
    ),
    (
        "api_response_field_add",
        "Plan how to add a response field and update related tests/documentation. Do not write files.",
        "api_change",
        ["main.go", "main_test.go", "README.md"],
        ["response", "field", "test"],
    ),
    (
        "api_backward_compat",
        "Explain how to keep a Go API change backward compatible in this repository. Do not write files.",
        "api_change",
        ["main.go", "README.md"],
        ["compatible", "api", "readme"],
    ),
    (
        "api_validation_rule",
        "Plan a parameter validation rule and identify validation/test locations. Do not write files.",
        "api_change",
        ["main.go", "main_test.go"],
        ["validation", "parameter", "test"],
    ),
    (
        "api_error_contract",
        "Describe how to standardize an API error contract and verify it with tests. Do not write files.",
        "api_change",
        ["main.go", "main_test.go"],
        ["error", "contract", "test"],
    ),
    (
        "error_nil_guard",
        "Find where a nil guard should be added before dereferencing values in Go code. Do not write files.",
        "error_handling",
        ["main.go"],
        ["nil", "guard", "panic"],
    ),
    (
        "error_wrap_context",
        "Suggest how to wrap errors with operation context without hiding the root cause. Do not write files.",
        "error_handling",
        ["main.go"],
        ["error", "context", "wrap"],
    ),
    (
        "error_return_consistency",
        "Review return paths for consistent Go error handling style. Do not write files.",
        "error_handling",
        ["main.go"],
        ["error", "return", "consistent"],
    ),
    (
        "error_validation_message",
        "Plan a clearer validation error message and explain test impact. Do not write files.",
        "error_handling",
        ["main.go", "main_test.go"],
        ["validation", "message", "test"],
    ),
    (
        "error_timeout_surface",
        "Explain how timeout errors should be surfaced and verified in a Go service. Do not write files.",
        "error_handling",
        ["main.go", "main_test.go"],
        ["timeout", "error", "verify"],
    ),
    (
        "config_go_mod_review",
        "Review go.mod and explain what it contributes to repair context. Do not write files.",
        "config",
        ["go.mod", "README.md"],
        ["module", "go.mod", "context"],
    ),
    (
        "config_dockerfile_plan",
        "Plan a Dockerfile build validation flow for this Go project. Do not write files.",
        "config",
        ["go.mod", "README.md"],
        ["docker", "build", "go"],
    ),
    (
        "config_makefile_plan",
        "Suggest Makefile targets for build, test, and vet validation. Do not write files.",
        "config",
        ["README.md", "go.mod"],
        ["makefile", "test", "vet"],
    ),
    (
        "config_readme_update",
        "Identify README updates needed after changing Calculate behavior. Do not write files.",
        "config",
        ["README.md", "main.go"],
        ["readme", "calculate", "behavior"],
    ),
    (
        "config_validation_command",
        "Choose a validation command for a Go repair task and explain why. Do not write files.",
        "config",
        ["go.mod", "main_test.go"],
        ["go test", "validation", "command"],
    ),
    (
        "refactor_extract_function",
        "Plan a small extract-function refactor around Calculate with low risk. Do not write files.",
        "refactor",
        ["main.go", "main_test.go"],
        ["refactor", "calculate", "test"],
    ),
    (
        "refactor_error_helper",
        "Plan a helper for repeated error handling while keeping changes local. Do not write files.",
        "refactor",
        ["main.go"],
        ["helper", "error", "local"],
    ),
    (
        "refactor_name_cleanup",
        "Suggest safer names for ambiguous variables and list files to review. Do not write files.",
        "refactor",
        ["main.go", "main_test.go"],
        ["name", "variable", "review"],
    ),
    (
        "refactor_testability",
        "Explain how to refactor the code to improve testability without changing behavior. Do not write files.",
        "refactor",
        ["main.go", "main_test.go"],
        ["testability", "behavior", "refactor"],
    ),
    (
        "refactor_scope_guard",
        "Define diff boundaries for a safe small refactor and how to reject out-of-scope changes. Do not write files.",
        "refactor",
        ["main.go", "main_test.go"],
        ["diff", "scope", "reject"],
    ),
]


GO_REPAIR_TASK_CASES: List[BenchmarkCase] = [
    BenchmarkCase(
        name=name,
        workspace_root=SAMPLE_GO_WORKSPACE,
        query=query,
        description=f"Go repair task catalog case: {name}",
        category=category,
        mode="single",
        expected_files=expected_files,
        expected_keywords=expected_keywords,
        expect_validation=False,
    )
    for name, query, category, expected_files, expected_keywords in _GO_REPAIR_CASE_SPECS
]


__all__ = ["GO_REPAIR_TASK_CASES"]

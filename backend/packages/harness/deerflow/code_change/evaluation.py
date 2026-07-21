from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from deerflow.code_change.models import TaskStatus
from deerflow.code_change.store import CodeChangeStore
from deerflow.code_change.worker import run_task_now


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    kind: str
    patch_text: str
    expected_value: int


def _patch(old: int, new: int, path: str = "app.py") -> str:
    return f"""diff --git a/{path} b/{path}
--- a/{path}
+++ b/{path}
@@ -1,2 +1,2 @@
 def value():
-    return {old}
+    return {new}
"""


def fixed_cases() -> list[EvaluationCase]:
    cases = [EvaluationCase(f"success-{index:02d}", "success", _patch(0, index), index) for index in range(1, 11)]
    cases.extend(EvaluationCase(f"invalid-{index:02d}", "invalid_context", _patch(999, index), index) for index in range(1, 5))
    cases.extend(EvaluationCase(f"unsafe-{index:02d}", "unsafe_path", _patch(0, index, f"../escape-{index}.py"), index) for index in range(1, 4))
    cases.extend(EvaluationCase(f"test-fail-{index:02d}", "test_failure", _patch(0, index), index + 100) for index in range(1, 4))
    return cases


def run_evaluation(output_dir: str | Path, cases: list[EvaluationCase] | None = None) -> dict:
    selected = cases or fixed_cases()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    work_root = Path(tempfile.mkdtemp(prefix="code-change-eval-"))
    records: list[dict] = []
    try:
        store = CodeChangeStore(work_root / "state", allowed_repo_roots=[work_root])
        for case in selected:
            repo = work_root / "repos" / case.case_id
            repo.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / "app.py").write_text("def value():\n    return 0\n", encoding="utf-8")
            project = store.create_project(
                case.case_id,
                str(repo),
                f'python3 -c "import app; assert app.value() == {case.expected_value}"',
            )
            started = time.perf_counter()
            task = run_task_now(store, project.project_id, f"evaluation case {case.case_id}", patch_text=case.patch_text)
            records.append(
                {
                    "case_id": case.case_id,
                    "kind": case.kind,
                    "status": str(task.status),
                    "patch_applied": bool(task.patch_result and task.patch_result.applied),
                    "tests_passed": bool(task.test_result and task.test_result.passed),
                    "duration_seconds": round(time.perf_counter() - started, 4),
                    "error": task.error,
                }
            )
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    total = len(records)
    unsafe = [record for record in records if record["kind"] == "unsafe_path"]
    metrics = {
        "task_count": total,
        "patch_apply_rate": _rate(sum(record["patch_applied"] for record in records), total),
        "test_pass_rate": _rate(sum(record["tests_passed"] for record in records), total),
        "task_success_rate": _rate(sum(record["status"] == str(TaskStatus.HANDOFF_READY) for record in records), total),
        "unsafe_patch_block_rate": _rate(sum(record["status"] == str(TaskStatus.FAILED) for record in unsafe), len(unsafe)),
        "mean_duration_seconds": round(sum(record["duration_seconds"] for record in records) / total, 4) if total else 0.0,
        "status_counts": dict(sorted(Counter(record["status"] for record in records).items())),
        "human_acceptance_rate": None,
    }
    result = {"suite": "code-change-fixed-v1", "metrics": metrics, "cases": records}
    (output / "evaluation.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "evaluation.md").write_text(_markdown(result), encoding="utf-8")
    return result


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _markdown(result: dict) -> str:
    metrics = result["metrics"]
    return f"""# Code Change Fixed Evaluation

- Suite: `{result["suite"]}`
- Tasks: {metrics["task_count"]}
- Patch apply rate: {metrics["patch_apply_rate"]:.2%}
- Test pass rate: {metrics["test_pass_rate"]:.2%}
- Task success rate: {metrics["task_success_rate"]:.2%}
- Unsafe patch block rate: {metrics["unsafe_patch_block_rate"]:.2%}
- Mean duration: {metrics["mean_duration_seconds"]:.4f}s
- Human acceptance rate: not measured; requires real reviewer decisions

This deterministic suite measures the external-patch workflow. It does not measure LLM retrieval recall, token cost, or autonomous patch generation.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic code-change evaluation suite")
    parser.add_argument("--output", default="artifacts/code-change-evaluation")
    args = parser.parse_args()
    run_evaluation(args.output)


if __name__ == "__main__":
    main()

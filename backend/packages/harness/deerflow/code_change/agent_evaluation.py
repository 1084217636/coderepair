from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from deerflow.code_change.models import PatchMode
from deerflow.code_change.store import CodeChangeStore
from deerflow.code_change.worker import run_task_now


@dataclass(frozen=True, slots=True)
class AgentEvaluationCase:
    case_id: str
    requirement: str
    files: dict[str, str]
    expected_files: tuple[str, ...] = ("app.py",)


def agent_cases() -> list[AgentEvaluationCase]:
    return [
        _case("bug-health-code", "Fix health_code so it returns HTTP status 200.", "def health_code():\n    return 500\n", "self.assertEqual(app.health_code(), 200)"),
        _case(
            "condition-negative-discount",
            "Make apply_discount raise ValueError when percent is negative; preserve normal discounts.",
            "def apply_discount(price, percent):\n    return price * (1 - percent / 100)\n",
            "self.assertEqual(app.apply_discount(100, 20), 80)\n        with self.assertRaises(ValueError): app.apply_discount(100, -1)",
        ),
        _case(
            "normalize-username",
            "Normalize usernames by stripping surrounding whitespace and converting to lowercase.",
            "def normalize_username(value):\n    return value\n",
            "self.assertEqual(app.normalize_username('  Alice  '), 'alice')",
        ),
        _case(
            "error-divide-zero",
            "Return None from safe_divide when the denominator is zero; otherwise return the quotient.",
            "def safe_divide(left, right):\n    return left / right\n",
            "self.assertIsNone(app.safe_divide(4, 0))\n        self.assertEqual(app.safe_divide(6, 2), 3)",
        ),
        _case(
            "default-port",
            "Make resolve_port return 8080 only when its input is None, otherwise preserve the supplied port.",
            "def resolve_port(value):\n    return value\n",
            "self.assertEqual(app.resolve_port(None), 8080)\n        self.assertEqual(app.resolve_port(0), 0)",
        ),
        _case(
            "boundary-adult",
            "Fix is_adult so age 18 is considered an adult.",
            "def is_adult(age):\n    return age > 18\n",
            "self.assertTrue(app.is_adult(18))\n        self.assertFalse(app.is_adult(17))",
        ),
        _case(
            "feature-unique-order",
            "Return unique values while preserving their first-seen order.",
            "def unique_values(values):\n    return sorted(set(values))\n",
            "self.assertEqual(app.unique_values([3, 1, 3, 2, 1]), [3, 1, 2])",
        ),
        _case(
            "parse-enabled",
            "Make parse_enabled accept case-insensitive true, yes and 1 as enabled; all other values are disabled.",
            "def parse_enabled(value):\n    return bool(value)\n",
            "self.assertTrue(app.parse_enabled('YES'))\n        self.assertTrue(app.parse_enabled('1'))\n        self.assertFalse(app.parse_enabled('false'))",
        ),
        _case(
            "clamp-range",
            "Clamp the input between the supplied minimum and maximum values.",
            "def clamp(value, minimum, maximum):\n    return min(value, maximum)\n",
            "self.assertEqual(app.clamp(-2, 0, 10), 0)\n        self.assertEqual(app.clamp(20, 0, 10), 10)\n        self.assertEqual(app.clamp(5, 0, 10), 5)",
        ),
        _case(
            "safe-mapping-get",
            "Make safe_get return the provided default when the key is missing.",
            "def safe_get(mapping, key, default=None):\n    return mapping[key]\n",
            "self.assertEqual(app.safe_get({'a': 1}, 'a', 9), 1)\n        self.assertEqual(app.safe_get({}, 'missing', 9), 9)",
        ),
        _case(
            "small-feature-greeting",
            "Change greeting to accept a name and return 'Hello, <name>!'.",
            "def greeting():\n    return 'Hello!'\n",
            "self.assertEqual(app.greeting('Ada'), 'Hello, Ada!')",
        ),
        AgentEvaluationCase(
            case_id="source-and-test-update",
            requirement="Change status_text from 'ready' to 'healthy' and update the repository unit test to assert the new value.",
            files={
                "app.py": "def status_text():\n    return 'ready'\n",
                "test_app.py": ("import unittest\nimport app\n\nclass AppTest(unittest.TestCase):\n    def test_behavior(self):\n        self.assertEqual(app.status_text(), 'ready')\n"),
            },
            expected_files=("app.py", "test_app.py"),
        ),
    ]


def run_agent_evaluation(
    output_dir: str | Path,
    *,
    model_name: str = "",
    cases: list[AgentEvaluationCase] | None = None,
) -> dict:
    selected = cases or agent_cases()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    work_root = Path(tempfile.mkdtemp(prefix="coding-agent-eval-"))
    records: list[dict] = []
    try:
        store = CodeChangeStore(work_root / "state", allowed_repo_roots=[work_root])
        for case in selected:
            repo = work_root / "repos" / case.case_id
            _create_repo(repo, case.files)
            project = store.create_project(case.case_id, str(repo), "python3 -m unittest -q")
            started = time.perf_counter()
            task = run_task_now(
                store,
                project.project_id,
                case.requirement,
                patch_mode=PatchMode.AGENT,
                agent_model_name=model_name,
            )
            retrieved_paths = {context.path for context in task.contexts[:5]}
            records.append(
                {
                    "case_id": case.case_id,
                    "status": str(task.status),
                    "tests_passed": bool(task.test_result and task.test_result.passed),
                    "retrieval_hit_at_5": all(path in retrieved_paths for path in case.expected_files),
                    "retrieved_paths": sorted(retrieved_paths),
                    "changed_files": list(task.agent_changed_files),
                    "retrieval_context_tokens": task.retrieval_context_tokens,
                    "input_tokens": task.agent_input_tokens,
                    "output_tokens": task.agent_output_tokens,
                    "duration_seconds": round(time.perf_counter() - started, 3),
                    "error": task.error,
                }
            )
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    count = len(records)
    metrics = {
        "task_count": count,
        "final_test_pass_rate": _rate(sum(item["tests_passed"] for item in records), count),
        "retrieval_recall_at_5": _rate(sum(item["retrieval_hit_at_5"] for item in records), count),
        "average_input_tokens": _average(item["input_tokens"] for item in records),
        "average_retrieval_context_tokens": _average(item["retrieval_context_tokens"] for item in records),
        "status_counts": {status: sum(item["status"] == status for item in records) for status in sorted({item["status"] for item in records})},
    }
    result = {
        "suite": "coding-agent-real-model-v1",
        "model_name": model_name or "config-default",
        "metrics": metrics,
        "cases": records,
    }
    (output / "coding-agent-evaluation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "coding-agent-evaluation.md").write_text(_markdown(result), encoding="utf-8")
    return result


def _case(case_id: str, requirement: str, source: str, assertion: str) -> AgentEvaluationCase:
    test_source = f"import unittest\nimport app\n\nclass AppTest(unittest.TestCase):\n    def test_behavior(self):\n        {assertion}\n"
    return AgentEvaluationCase(case_id, requirement, {"app.py": source, "test_app.py": test_source})


def _create_repo(repo: Path, files: dict[str, str]) -> None:
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=Agent Evaluation", "-c", "user.email=eval@example.com", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Agent Evaluation", "-c", "user.email=eval@example.com", "commit", "-q", "-m", "fixture"],
        cwd=repo,
        check=True,
    )


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _average(values) -> float:
    selected = list(values)
    return round(sum(selected) / len(selected), 2) if selected else 0.0


def _markdown(result: dict) -> str:
    metrics = result["metrics"]
    rows = "\n".join(f"| {case['case_id']} | {case['tests_passed']} | {case['retrieval_hit_at_5']} | {case['input_tokens']} |" for case in result["cases"])
    return f"""# Coding Agent Evaluation

- Model: `{result["model_name"]}`
- Task count: {metrics["task_count"]}
- Final test pass rate: {metrics["final_test_pass_rate"]:.2%}
- Retrieval Recall@5: {metrics["retrieval_recall_at_5"]:.2%}
- Average input tokens: {metrics["average_input_tokens"]:.2f}

| Case | Tests passed | Retrieval hit@5 | Input tokens |
| --- | ---: | ---: | ---: |
{rows}

This suite runs the real Agent → Tool → Patch → Workspace → Test path. The separate 20-case external-patch suite remains a deterministic regression gate and is not counted as model success.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real-model Coding Agent evaluation")
    parser.add_argument("--output", default="artifacts/coding-agent-evaluation")
    parser.add_argument("--model", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    cases = agent_cases()[: args.limit or None]
    result = run_agent_evaluation(args.output, model_name=args.model, cases=cases)
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .context import BranchContextBuilder
from .models import AnchorSelection


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    anchor: str
    root_summary: str
    branch_history: list[str]
    code_context: list[str]
    question: str
    full_history: list[str]


def run_benchmark(cases: list[BenchmarkCase], *, token_budget: int = 6_000) -> dict[str, Any]:
    builder = BranchContextBuilder(token_budget=token_budget)
    results: list[dict[str, Any]] = []
    for case in cases:
        anchor = AnchorSelection(text=case.anchor)
        full_prompt = "\n".join([*case.full_history, case.anchor, case.question])
        bounded = builder.build(
            anchor,
            root_summary=case.root_summary,
            branch_history=case.branch_history,
            code_context=case.code_context,
            current_question=case.question,
        )
        bounded_prompt = bounded.to_prompt()
        results.append(
            {
                "case_id": case.case_id,
                "full_history_chars": len(full_prompt),
                "anchored_context_chars": len(bounded_prompt),
                "char_reduction_ratio": round(1 - len(bounded_prompt) / max(1, len(full_prompt)), 4),
                "estimated_tokens": bounded.estimated_tokens,
                "anchor_preserved": case.anchor in bounded_prompt,
                "question_preserved": case.question in bounded_prompt,
                "truncated": bounded.truncated,
            }
        )
    return {
        "benchmark": "anchored-context-v1",
        "case_count": len(results),
        "token_budget": token_budget,
        "results": results,
        "anchor_preservation_rate": sum(item["anchor_preserved"] for item in results) / max(1, len(results)),
        "question_preservation_rate": sum(item["question_preserved"] for item in results) / max(1, len(results)),
        "mean_char_reduction_ratio": sum(item["char_reduction_ratio"] for item in results) / max(1, len(results)),
    }


def default_cases() -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            case_id="cache-consistency-01",
            anchor="这里为什么选择删除缓存，而不是更新缓存？",
            root_summary="The main task fixed stale reads in the user update path.",
            branch_history=["The agent found a cache-aside repository.", "The user asked about invalidation."],
            code_context=["cache.py: delete the key after the database commit", "test_cache.py: assert the next read reloads data"],
            question="那如果这里以后改成高并发呢？",
            full_history=[f"old main message {index}: unrelated repository discussion" for index in range(80)],
        )
    ]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Compare full history with bounded Anchored Branch context")
    parser.add_argument("--output", type=Path, default=Path("artifacts/anchored-context-benchmark.json"))
    args = parser.parse_args()
    payload = run_benchmark(default_cases())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

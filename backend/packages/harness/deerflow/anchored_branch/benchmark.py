from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .context import BranchContextBuilder
from .models import AnchorSelection, BranchContextStrategy


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    anchor: str
    main_task_summary: str
    branch_history: list[str]
    code_context: list[str]
    question: str
    full_history: list[str]
    required_facts: list[str]
    irrelevant_markers: list[str]
    answers: dict[str, str] | None = None


def run_benchmark(cases: list[BenchmarkCase], *, token_budget: int = 6_000) -> dict[str, Any]:
    builder = BranchContextBuilder(token_budget=token_budget)
    results: list[dict[str, Any]] = []
    for case in cases:
        anchor = AnchorSelection(text=case.anchor)
        strategies: dict[str, Any] = {}
        for strategy in BranchContextStrategy:
            context = builder.build(
                anchor,
                main_task_summary=case.main_task_summary,
                relevant_main_context=case.code_context,
                main_history=case.full_history,
                branch_history=case.branch_history,
                code_context=case.code_context,
                current_question=case.question,
                strategy=strategy,
            )
            prompt = context.to_prompt()
            required_present = sum(fact.lower() in prompt.lower() for fact in case.required_facts)
            irrelevant_present = sum(marker.lower() in prompt.lower() for marker in case.irrelevant_markers)
            answer = (case.answers or {}).get(str(strategy))
            answer_correct = None
            if answer is not None:
                answer_correct = all(fact.lower() in answer.lower() for fact in case.required_facts)
            strategies[str(strategy)] = {
                "prompt_tokens": context.estimated_tokens,
                "background_omission_rate": round(1 - required_present / max(1, len(case.required_facts)), 4),
                "irrelevant_context_ratio": round(irrelevant_present / max(1, len(case.irrelevant_markers)), 4),
                "anchor_preserved": case.anchor in prompt,
                "branch_history_preserved": all(item in prompt for item in case.branch_history[-2:]),
                "answer_correct": answer_correct,
                "truncated": context.truncated,
            }
        results.append({"case_id": case.case_id, "strategies": strategies})
    return {
        "benchmark": "anchored-context-strategies-v2",
        "case_count": len(results),
        "token_budget": token_budget,
        "results": results,
        "note": "answer_correct is null until real model outputs are supplied; context metrics are never presented as model accuracy",
    }


def default_cases() -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            case_id="cache-consistency-01",
            anchor="这里为什么选择删除缓存，而不是更新缓存？",
            main_task_summary="The main task fixed stale reads in the user update path.",
            branch_history=["The user asked why deletion was chosen.", "The branch compared two write paths."],
            code_context=["cache.py: cache-aside deletes the key after the database commit", "test_cache.py: assert the next read reloads data"],
            question="那如果这里以后改成高并发呢？",
            full_history=[f"old main message {index}: unrelated repository discussion" for index in range(80)],
            required_facts=["cache-aside", "database commit"],
            irrelevant_markers=["unrelated repository discussion"],
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

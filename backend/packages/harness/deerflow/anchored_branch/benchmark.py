from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from deerflow.anchored_branch.context import BranchContext, BranchContextBuilder
from deerflow.anchored_branch.models import AnchorSelection, BranchContextStrategy
from deerflow.models import create_chat_model
from deerflow.utils.messages import message_to_text


@dataclass(frozen=True, slots=True)
class AnchoredEvaluationCase:
    case_id: str
    anchor: str
    main_task_summary: str
    relevant_main_context: list[str]
    branch_history: list[str]
    question: str
    expected_answer: str
    full_history: list[str]
    required_facts: list[str]
    code_context: list[str]


def evaluation_cases() -> list[AnchoredEvaluationCase]:
    return [
        _case("cache-source", "delete cache after commit", "MySQL is the source of truth; Redis is cache-aside.", "Which component is authoritative? A Redis B MySQL C Browser D Kafka", "B"),
        _case(
            "ack-meaning",
            "acked_seq advances on delivery confirmation",
            "ACK means network delivery confirmation, while read_seq means the user opened the conversation.",
            "Which field represents opening the conversation? A last_seq B acked_seq C read_seq D retry_seq",
            "C",
        ),
        _case(
            "lease-owner", "processing(owner, lease)", "The lease lets another consumer recover work after the current owner stops heartbeating.", "What primarily enables recovery? A owner name B lease expiry C file path D HTTP cookie", "B"
        ),
        _case(
            "workspace-boundary",
            "apply patch inside workspace",
            "The registered source checkout must remain unchanged; only the isolated workspace may be modified.",
            "Where may the candidate patch be applied? A source checkout B workspace C browser D Redis",
            "B",
        ),
        _case(
            "tool-boundary",
            "submit_patch exactly once",
            "The Agent can search and read, but only the deterministic Worker can apply patches and execute tests.",
            "Who executes tests? A model B browser C deterministic Worker D retriever",
            "C",
        ),
        _case(
            "origin-security",
            "validate WebSocket Origin",
            "Origin validation protects browser WebSocket handshakes from untrusted web pages; native clients require a separate policy.",
            "Which client is directly protected by Origin checking? A browser page B MySQL client C Kafka broker D cron job",
            "A",
        ),
        _case(
            "kafka-commit",
            "CommitMessages after retry or DLQ persistence",
            "Offsets are committed only after delivery succeeds or failed work is durably handed to retry/DLQ.",
            "When is the offset committed? A before delivery B after durable outcome C at login D at compile time",
            "B",
        ),
        _case(
            "jwt-property",
            "verify token signature",
            "JWT signatures provide integrity and authenticity, not confidentiality; the payload is readable.",
            "What does the signature primarily provide? A encryption B compression C integrity D database locking",
            "C",
        ),
        _case(
            "context-isolation",
            "start_run(child_thread_id)",
            "Branch messages and ToolMessages use the Child Checkpoint; Main is read only when the Branch snapshot is created.",
            "Where is Branch history persisted? A Main Checkpoint B Child Checkpoint C Git index D JWT",
            "B",
        ),
        _case(
            "retrieval-fallback",
            "semantic=unavailable",
            "When the embedding provider fails, retrieval continues with lexical and symbol signals.",
            "What is the fallback? A stop the task B full repository copy C lexical plus symbol D random files",
            "C",
        ),
        _case(
            "token-budget",
            "Anchor and question are hard preserved",
            "Optional context is trimmed first; if the Anchor and question cannot fit, context construction fails explicitly.",
            "What is trimmed first? A Anchor B current question C optional context D answer label",
            "C",
        ),
        _case(
            "typed-patch",
            "typed submit tool",
            "Natural-language claims are not accepted as a code change; the Agent must submit a unified diff through the typed Tool.",
            "What artifact enters deterministic validation? A prose B unified diff C screenshot D SQL row",
            "B",
        ),
    ]


def _case(case_id: str, anchor: str, fact: str, question: str, expected: str) -> AnchoredEvaluationCase:
    distractors = [
        "Earlier the team discussed UI colors and release naming.",
        "An unrelated service uses a different storage and deployment policy.",
        "The previous answer also contained general Python style suggestions.",
    ]
    return AnchoredEvaluationCase(
        case_id=case_id,
        anchor=anchor,
        main_task_summary=f"Explain the engineering behavior around {case_id}.",
        relevant_main_context=[fact],
        branch_history=["human: Please focus only on the selected implementation detail."],
        question=f"{question}. Answer with exactly one letter: A, B, C, or D.",
        expected_answer=expected,
        full_history=[distractors[0], fact, *distractors[1:]],
        required_facts=[fact],
        code_context=[],
    )


def build_strategy_contexts(
    case: AnchoredEvaluationCase,
    *,
    token_budget: int = 6_000,
) -> dict[BranchContextStrategy, BranchContext]:
    builder = BranchContextBuilder(token_budget=token_budget)
    anchor = AnchorSelection(text=case.anchor)
    return {
        strategy: builder.build(
            anchor,
            main_task_summary=case.main_task_summary,
            relevant_main_context=case.relevant_main_context,
            main_history=case.full_history,
            branch_history=case.branch_history,
            code_context=case.code_context,
            current_question=case.question,
            strategy=strategy,
        )
        for strategy in BranchContextStrategy
    }


def run_anchored_evaluation(
    output_dir: str | Path,
    *,
    model_name: str = "",
    cases: list[AnchoredEvaluationCase] | None = None,
    token_budget: int = 6_000,
) -> dict[str, Any]:
    selected = cases or evaluation_cases()
    model = create_chat_model(name=model_name or None, thinking_enabled=False, attach_tracing=False, temperature=0)
    records: list[dict[str, Any]] = []
    for case in selected:
        for strategy, context in build_strategy_contexts(case, token_budget=token_budget).items():
            response = model.invoke(
                [
                    SystemMessage(content=context.to_prompt()),
                    HumanMessage(content=case.question),
                ]
            )
            answer_text = message_to_text(response).strip()
            usage = getattr(response, "usage_metadata", None) or {}
            prompt_tokens = int(usage.get("input_tokens") or context.estimated_tokens) if isinstance(usage, dict) else context.estimated_tokens
            required_present = sum(fact.lower() in context.to_prompt().lower() for fact in case.required_facts)
            parsed = parse_choice(answer_text)
            records.append(
                {
                    "case_id": case.case_id,
                    "strategy": str(strategy),
                    "expected_answer": case.expected_answer,
                    "parsed_answer": parsed,
                    "answer_text": answer_text,
                    "correct": parsed == case.expected_answer,
                    "prompt_tokens": prompt_tokens,
                    "background_omission_rate": round(1 - required_present / max(1, len(case.required_facts)), 4),
                }
            )

    strategies: dict[str, dict[str, float | int]] = {}
    for strategy in BranchContextStrategy:
        rows = [record for record in records if record["strategy"] == str(strategy)]
        strategies[str(strategy)] = {
            "case_count": len(rows),
            "answer_correct_rate": _rate(sum(row["correct"] for row in rows), len(rows)),
            "average_prompt_tokens": _average(row["prompt_tokens"] for row in rows),
            "background_omission_rate": _average(row["background_omission_rate"] for row in rows),
        }
    result = {
        "suite": "anchored-context-real-model-v1",
        "model_name": model_name or "config-default",
        "token_budget": token_budget,
        "strategies": strategies,
        "cases": records,
    }
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "anchored-context-evaluation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "anchored-context-evaluation.md").write_text(_markdown(result), encoding="utf-8")
    return result


def parse_choice(text: str) -> str:
    stripped = text.strip().upper()
    if stripped[:1] in {"A", "B", "C", "D"}:
        return stripped[0]
    match = re.search(r"(?:ANSWER|答案)\s*[:：]?\s*([ABCD])\b", stripped)
    return match.group(1) if match else ""


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _average(values) -> float:
    selected = list(values)
    return round(sum(selected) / len(selected), 2) if selected else 0.0


def _markdown(result: dict[str, Any]) -> str:
    rows = "\n".join(f"| {name} | {metrics['answer_correct_rate']:.2%} | {metrics['average_prompt_tokens']:.2f} | {metrics['background_omission_rate']:.2%} |" for name, metrics in result["strategies"].items())
    return f"""# Anchored Context Evaluation

- Model: `{result["model_name"]}`
- Cases per strategy: {next(iter(result["strategies"].values()))["case_count"] if result["strategies"] else 0}

| Strategy | Correct Rate | Avg Prompt Tokens | Background Omission |
| --- | ---: | ---: | ---: |
{rows}

Every row comes from real model responses with the same model and temperature. Full History, Anchor Only and Anchored Context differ only in context construction.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real-model Anchored Context evaluation")
    parser.add_argument("--output", default="artifacts/anchored-context-evaluation")
    parser.add_argument("--model", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--token-budget", type=int, default=6_000)
    args = parser.parse_args()
    cases = evaluation_cases()[: args.limit or None]
    result = run_anchored_evaluation(
        args.output,
        model_name=args.model,
        cases=cases,
        token_budget=args.token_budget,
    )
    print(json.dumps(result["strategies"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

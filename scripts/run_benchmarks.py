#!/usr/bin/env python3
"""
运行默认 benchmark 套件。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import CodeRepairPlatform
from evaluation import (
    BenchmarkSuiteRunner,
    BenchmarkVariant,
    DEFAULT_BENCHMARK_CASES,
    GO_REPAIR_TASK_CASES,
)


PRESET_VARIANTS: Dict[str, Dict[str, object]] = {
    "keyword_baseline": {
        "LEXICAL_BACKEND": "keyword",
        "RERANK_ENABLED": False,
    },
    "bm25_only": {
        "LEXICAL_BACKEND": "bm25",
        "RERANK_ENABLED": False,
    },
    "bm25_rerank": {
        "LEXICAL_BACKEND": "bm25",
        "RERANK_ENABLED": True,
    },
}

BENCHMARK_SUITES = {
    "default": DEFAULT_BENCHMARK_CASES,
    "go-repair": GO_REPAIR_TASK_CASES,
}


def select_cases(
    case_name: str | None = None,
    limit: int | None = None,
    suite_name: str = "default",
):
    if suite_name not in BENCHMARK_SUITES:
        raise SystemExit(f"unknown suite: {suite_name}")
    cases = BENCHMARK_SUITES[suite_name]
    if case_name:
        cases = [case for case in cases if case.name == case_name]
        if not cases:
            raise SystemExit(f"case not found: {case_name}")
    if limit is not None and limit > 0:
        cases = cases[:limit]
    return cases


def _base_overrides(args: argparse.Namespace) -> Dict[str, object]:
    overrides: Dict[str, object] = {}
    if args.rag_backend:
        overrides["RAG_BACKEND"] = args.rag_backend
    if args.lexical_backend:
        overrides["LEXICAL_BACKEND"] = args.lexical_backend
    if args.bm25_k1 is not None:
        overrides["BM25_K1"] = args.bm25_k1
    if args.bm25_b is not None:
        overrides["BM25_B"] = args.bm25_b
    if args.rerank is not None:
        overrides["RERANK_ENABLED"] = args.rerank
    if args.rerank_top_n is not None:
        overrides["RERANK_TOP_N"] = args.rerank_top_n
    return overrides


def build_variants(args: argparse.Namespace) -> List[BenchmarkVariant]:
    variant_names = [name.strip() for name in (args.variants or "").split(",") if name.strip()]
    if not variant_names:
        variant_names = ["keyword_baseline", "bm25_only", "bm25_rerank"]

    global_overrides = {}
    if args.rag_backend:
        global_overrides["RAG_BACKEND"] = args.rag_backend
    if args.bm25_k1 is not None:
        global_overrides["BM25_K1"] = args.bm25_k1
    if args.bm25_b is not None:
        global_overrides["BM25_B"] = args.bm25_b
    if args.rerank_top_n is not None:
        global_overrides["RERANK_TOP_N"] = args.rerank_top_n

    variants: List[BenchmarkVariant] = []
    for name in variant_names:
        if name not in PRESET_VARIANTS:
            raise SystemExit(f"unknown variant: {name}")
        settings_overrides = {
            **PRESET_VARIANTS[name],
            **global_overrides,
        }
        variants.append(
            BenchmarkVariant(
                name=name,
                description=f"benchmark preset: {name}",
                settings_overrides=settings_overrides,
            )
        )
    return variants


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CodeRepair benchmark suite")
    parser.add_argument("--provider", default=None, help="Override LLM provider")
    parser.add_argument("--model", default=None, help="Override LLM model")
    parser.add_argument("--temperature", type=float, default=None, help="Override temperature")
    parser.add_argument(
        "--rag-backend",
        choices=["lexical", "vector", "hybrid"],
        default=None,
        help="覆盖 benchmark 运行时的 RAG backend",
    )
    parser.add_argument(
        "--lexical-backend",
        choices=["keyword", "bm25"],
        default=None,
        help="覆盖单套件运行时的词法检索实现",
    )
    parser.add_argument("--bm25-k1", type=float, default=None, help="覆盖 BM25 k1 参数")
    parser.add_argument("--bm25-b", type=float, default=None, help="覆盖 BM25 b 参数")
    parser.add_argument("--rerank-top-n", type=int, default=None, help="覆盖 rerank 候选池大小")
    parser.add_argument(
        "--validation-mode",
        choices=["auto", "local", "docker"],
        default="auto",
        help="Validation mode used for benchmark cases",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Force running validation for all benchmark cases",
    )
    parser.add_argument(
        "--rerank",
        dest="rerank",
        action="store_true",
        default=None,
        help="单套件运行时显式开启 rerank",
    )
    parser.add_argument(
        "--no-rerank",
        dest="rerank",
        action="store_false",
        help="单套件运行时显式关闭 rerank",
    )
    parser.add_argument("--case", default=None, help="只运行指定 case 名")
    parser.add_argument("--limit", type=int, default=None, help="只运行前 N 个 case")
    parser.add_argument(
        "--suite",
        choices=sorted(BENCHMARK_SUITES.keys()),
        default="default",
        help="选择 benchmark 套件",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="运行多 variant 对比，输出 delta 报告",
    )
    parser.add_argument(
        "--variants",
        default=None,
        help="对比模式下运行哪些 preset variant，用逗号分隔；默认 keyword_baseline,bm25_only,bm25_rerank",
    )
    args = parser.parse_args()

    runner = BenchmarkSuiteRunner(
        platform_factory=lambda: CodeRepairPlatform(
            provider=args.provider,
            model=args.model,
            temperature=args.temperature,
        )
    )
    cases = select_cases(case_name=args.case, limit=args.limit, suite_name=args.suite)

    if args.compare:
        report = runner.run_comparison(
            build_variants(args),
            cases=cases,
            validate=args.validate,
            validation_mode=args.validation_mode,
        )
        summary = {
            item["variant"]["name"]: item["aggregate"]
            for item in report["variants"]
        }
        payload = {
            "baseline_variant": report["baseline_variant"],
            "variant_aggregates": summary,
            "deltas": report["deltas"],
        }
    else:
        report = runner.run_suite(
            cases=cases,
            validate=args.validate,
            validation_mode=args.validation_mode,
            settings_overrides=_base_overrides(args),
        )
        payload = report["aggregate"]

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

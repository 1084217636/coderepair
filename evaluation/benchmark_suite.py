"""
Benchmark 套件：让单智能体 / 多智能体 / 检索链具备可比较的评估入口。
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from config import settings
from core.logger import get_logger
from .metrics import BenchmarkCase, RunMetricsEvaluator

logger = get_logger(__name__)


@dataclass
class BenchmarkVariant:
    """同一批 case 的不同检索/执行配置。"""

    name: str
    description: str = ""
    settings_overrides: Dict[str, Any] = field(default_factory=dict)


DEFAULT_BENCHMARK_CASES: List[BenchmarkCase] = [
    BenchmarkCase(
        name="project_overview_single",
        workspace_root=str(settings.PLATFORM_ROOT / "examples/sample_go_project"),
        query="请说明这个 Go 项目的入口、核心函数和潜在问题，不要修改代码。",
        description="单智能体项目总览问答",
        category="analysis",
        mode="single",
        expected_files=["main.go", "README.md", "go.mod"],
        expected_keywords=["main", "calculate", "bug"],
    ),
    BenchmarkCase(
        name="project_overview_multi",
        workspace_root=str(settings.PLATFORM_ROOT / "examples/sample_go_project"),
        query="请说明这个 Go 项目的入口、核心函数和潜在问题，不要修改代码。",
        description="多智能体项目总览问答",
        category="analysis",
        mode="multi",
        expected_files=["main.go", "README.md", "go.mod"],
        expected_keywords=["main", "calculate", "bug"],
    ),
    BenchmarkCase(
        name="calculate_bug_single",
        workspace_root=str(settings.PLATFORM_ROOT / "examples/sample_go_project"),
        query="请定位 Calculate 函数的问题并给出修复建议，不要直接写文件。",
        description="单智能体缺陷定位",
        category="bug_fix",
        mode="single",
        expected_files=["main.go", "main_test.go"],
        expected_keywords=["calculate", "result", "return"],
    ),
    BenchmarkCase(
        name="calculate_bug_multi",
        workspace_root=str(settings.PLATFORM_ROOT / "examples/sample_go_project"),
        query="请定位 Calculate 函数的问题并给出修复建议，不要直接写文件。",
        description="多智能体缺陷定位",
        category="bug_fix",
        mode="multi",
        expected_files=["main.go", "main_test.go"],
        expected_keywords=["calculate", "result", "return"],
    ),
    BenchmarkCase(
        name="engineering_file_review",
        workspace_root=str(settings.PLATFORM_ROOT / "examples/sample_go_project"),
        query="请说明 go.mod 和 README 对理解这个项目分别提供了什么上下文信息。",
        description="工程文件进入检索链",
        category="context",
        mode="single",
        expected_files=["go.mod", "README.md"],
        expected_keywords=["module", "readme", "context"],
    ),
]


class BenchmarkSuiteRunner:
    """跑一组固定 case，沉淀成可比较的结果。"""

    def __init__(self, platform_factory: Callable[[], Any], output_root: Optional[Path] = None):
        self.platform_factory = platform_factory
        self.output_root = output_root or (settings.ARTIFACTS_ROOT / "benchmark_reports")
        self.output_root.mkdir(parents=True, exist_ok=True)

    def run_case(
        self,
        case: BenchmarkCase,
        *,
        validate: Optional[bool] = None,
        validation_mode: str = "auto",
    ) -> Dict[str, Any]:
        platform = self.platform_factory()
        result = platform.run(
            user_input=case.query,
            workspace_root=case.workspace_root,
            validate=case.expect_validation if validate is None else validate,
            mode=case.mode,
            validation_mode=validation_mode,
            focus_file=case.focus_file,
        )
        return self._build_case_report(case, result)

    def run_suite(
        self,
        cases: Optional[Iterable[BenchmarkCase]] = None,
        *,
        validate: Optional[bool] = None,
        validation_mode: str = "auto",
        settings_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        benchmark_cases = list(cases or DEFAULT_BENCHMARK_CASES)
        if settings_overrides:
            with self._override_settings(settings_overrides):
                suite_report = self._build_suite_report(
                    benchmark_cases,
                    validate=validate,
                    validation_mode=validation_mode,
                    suite_name="default_benchmark_suite",
                )
        else:
            suite_report = self._build_suite_report(
                benchmark_cases,
                validate=validate,
                validation_mode=validation_mode,
                suite_name="default_benchmark_suite",
            )
        self._save_suite_report(suite_report)
        return suite_report

    def run_comparison(
        self,
        variants: Iterable[BenchmarkVariant],
        *,
        cases: Optional[Iterable[BenchmarkCase]] = None,
        validate: Optional[bool] = None,
        validation_mode: str = "auto",
    ) -> Dict[str, Any]:
        benchmark_cases = list(cases or DEFAULT_BENCHMARK_CASES)
        benchmark_variants = list(variants)
        if not benchmark_variants:
            raise ValueError("run_comparison 至少需要一个 BenchmarkVariant")

        variant_reports = []
        for variant in benchmark_variants:
            with self._override_settings(variant.settings_overrides):
                suite_report = self._build_suite_report(
                    benchmark_cases,
                    validate=validate,
                    validation_mode=validation_mode,
                    suite_name=f"comparison::{variant.name}",
                )
            variant_reports.append(
                {
                    "variant": asdict(variant),
                    "aggregate": suite_report["aggregate"],
                    "by_mode": suite_report["by_mode"],
                    "cases": suite_report["cases"],
                }
            )

        baseline = variant_reports[0]
        comparison_report = {
            "generated_at": datetime.now().isoformat(),
            "comparison_name": "retrieval_variant_comparison",
            "case_count": len(benchmark_cases),
            "baseline_variant": baseline["variant"]["name"],
            "variants": variant_reports,
            "deltas": {
                report["variant"]["name"]: self._build_variant_delta(
                    baseline["aggregate"],
                    report["aggregate"],
                )
                for report in variant_reports
            },
        }
        self._save_comparison_report(comparison_report)
        return comparison_report

    def _build_suite_report(
        self,
        benchmark_cases: List[BenchmarkCase],
        *,
        validate: Optional[bool],
        validation_mode: str,
        suite_name: str,
    ) -> Dict[str, Any]:
        case_reports = [
            self.run_case(case, validate=validate, validation_mode=validation_mode)
            for case in benchmark_cases
        ]
        aggregate = RunMetricsEvaluator.aggregate_suite(
            report["evaluation_output"] for report in case_reports
        )
        by_mode = self._aggregate_by_mode(case_reports)
        return {
            "generated_at": datetime.now().isoformat(),
            "suite_name": suite_name,
            "case_count": len(case_reports),
            "aggregate": aggregate,
            "by_mode": by_mode,
            "cases": case_reports,
        }

    def _build_case_report(self, case: BenchmarkCase, result: Dict[str, Any]) -> Dict[str, Any]:
        retrieval_results = result.get("evaluation_output", {})
        summary = self._match_expectations(case, result)
        return {
            "case": asdict(case),
            "session_id": result.get("session_id"),
            "execution_mode": result.get("execution_mode"),
            "llm_config": result.get("llm_config"),
            "evaluation_output": retrieval_results,
            "expectation_check": summary,
        }

    def _match_expectations(self, case: BenchmarkCase, result: Dict[str, Any]) -> Dict[str, Any]:
        session_id = result.get("session_id")
        retrieval_path = settings.ARTIFACTS_ROOT / f"session_{session_id}" / "03_retrieval_results.json"
        retrieved_files: List[str] = []
        if retrieval_path.exists():
            retrieval_payload = json.loads(retrieval_path.read_text(encoding="utf-8"))
            retrieved_files = [
                item.get("relative_path", "")
                for item in retrieval_payload.get("results", [])
            ]

        llm_response = (result.get("llm_response") or "").lower()
        expected_files = case.expected_files or []
        expected_keywords = case.expected_keywords or []

        matched_files = [
            expected for expected in expected_files
            if any(expected in file_path for file_path in retrieved_files)
        ]
        matched_keywords = [
            keyword for keyword in expected_keywords
            if keyword.lower() in llm_response
        ]
        return {
            "retrieved_files": retrieved_files,
            "expected_files": expected_files,
            "matched_files": matched_files,
            "file_hit_rate": round(len(matched_files) / len(expected_files), 4) if expected_files else None,
            "expected_keywords": expected_keywords,
            "matched_keywords": matched_keywords,
            "keyword_hit_rate": round(len(matched_keywords) / len(expected_keywords), 4) if expected_keywords else None,
        }

    def _aggregate_by_mode(self, case_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for report in case_reports:
            grouped.setdefault(report["execution_mode"], []).append(report)

        summary: Dict[str, Any] = {}
        for mode, reports in grouped.items():
            summary[mode] = {
                "cases": len(reports),
                "aggregate": RunMetricsEvaluator.aggregate_suite(
                    item["evaluation_output"] for item in reports
                ),
                "avg_file_hit_rate": self._average_nullable(
                    item["expectation_check"].get("file_hit_rate") for item in reports
                ),
                "avg_keyword_hit_rate": self._average_nullable(
                    item["expectation_check"].get("keyword_hit_rate") for item in reports
                ),
            }
        return summary

    @staticmethod
    def _average_nullable(values: Iterable[Optional[float]]) -> Optional[float]:
        filtered = [value for value in values if value is not None]
        if not filtered:
            return None
        return round(sum(filtered) / len(filtered), 4)

    def _save_suite_report(self, report: Dict[str, Any]) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = self.output_root / f"benchmark_{timestamp}.json"
        md_path = self.output_root / f"benchmark_{timestamp}.md"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(self._render_markdown(report), encoding="utf-8")
        logger.info("[Benchmark] 报告已生成 | json=%s | md=%s", json_path, md_path)

    def _save_comparison_report(self, report: Dict[str, Any]) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = self.output_root / f"benchmark_compare_{timestamp}.json"
        md_path = self.output_root / f"benchmark_compare_{timestamp}.md"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(self._render_comparison_markdown(report), encoding="utf-8")
        logger.info("[Benchmark] 对比报告已生成 | json=%s | md=%s", json_path, md_path)

    @staticmethod
    def _build_variant_delta(baseline: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
        delta_fields = [
            "avg_retrieval_hit_rate",
            "avg_primary_score",
            "avg_retrieval_score",
            "avg_retrieved_code_ratio",
            "validation_pass_rate",
            "repair_success_rate",
        ]
        deltas: Dict[str, Any] = {}
        for field in delta_fields:
            baseline_value = baseline.get(field)
            current_value = current.get(field)
            if isinstance(baseline_value, (int, float)) and isinstance(current_value, (int, float)):
                deltas[field] = round(current_value - baseline_value, 4)
            else:
                deltas[field] = None
        return deltas

    @contextmanager
    def _override_settings(self, overrides: Dict[str, Any]):
        original_values = {
            key: getattr(settings, key)
            for key in overrides
        }
        try:
            for key, value in overrides.items():
                setattr(settings, key, value)
            yield
        finally:
            for key, value in original_values.items():
                setattr(settings, key, value)

    def _render_markdown(self, report: Dict[str, Any]) -> str:
        parts = ["# Benchmark Report", ""]
        parts.append(f"- Generated At: {report['generated_at']}")
        parts.append(f"- Case Count: {report['case_count']}")
        aggregate = report["aggregate"]
        parts.append(f"- Avg Retrieval Hit Rate: {aggregate['avg_retrieval_hit_rate']}")
        parts.append(f"- Avg Primary Score: {aggregate['avg_primary_score']}")
        parts.append(f"- Avg Retrieval Score: {aggregate['avg_retrieval_score']}")
        parts.append(f"- Avg Retrieved Code Ratio: {aggregate['avg_retrieved_code_ratio']}")
        parts.append(f"- Rerank Usage Rate: {aggregate['rerank_usage_rate']}")
        parts.append(f"- Validation Pass Rate: {aggregate['validation_pass_rate']}")
        parts.append(f"- Repair Success Rate: {aggregate['repair_success_rate']}")
        parts.append("")
        parts.append("## By Mode")
        parts.append("")
        for mode, summary in report["by_mode"].items():
            parts.append(f"### {mode}")
            parts.append(f"- Cases: {summary['cases']}")
            parts.append(f"- Avg File Hit Rate: {summary['avg_file_hit_rate']}")
            parts.append(f"- Avg Keyword Hit Rate: {summary['avg_keyword_hit_rate']}")
            parts.append(f"- Avg Retrieval Hit Rate: {summary['aggregate']['avg_retrieval_hit_rate']}")
            parts.append(f"- Avg Primary Score: {summary['aggregate']['avg_primary_score']}")
            parts.append(f"- Avg Retrieval Score: {summary['aggregate']['avg_retrieval_score']}")
            parts.append("")

        parts.append("## Cases")
        parts.append("")
        for item in report["cases"]:
            case = item["case"]
            parts.append(f"### {case['name']}")
            parts.append(f"- Description: {case['description']}")
            parts.append(f"- Mode: {item['execution_mode']}")
            parts.append(f"- Session ID: {item['session_id']}")
            parts.append(f"- Retrieval Hit Rate: {item['evaluation_output'].get('retrieval_hit_rate')}")
            parts.append(f"- Primary Score: {item['evaluation_output'].get('primary_score')}")
            parts.append(f"- Avg Retrieval Score: {item['evaluation_output'].get('avg_retrieval_score')}")
            parts.append(f"- Lexical Backend: {item['evaluation_output'].get('lexical_backend')}")
            parts.append(f"- Rerank Enabled: {item['evaluation_output'].get('rerank_enabled')}")
            parts.append(f"- File Hit Rate: {item['expectation_check'].get('file_hit_rate')}")
            parts.append(f"- Keyword Hit Rate: {item['expectation_check'].get('keyword_hit_rate')}")
            parts.append("")
        return "\n".join(parts)

    def _render_comparison_markdown(self, report: Dict[str, Any]) -> str:
        parts = ["# Benchmark Comparison", ""]
        parts.append(f"- Generated At: {report['generated_at']}")
        parts.append(f"- Baseline Variant: {report['baseline_variant']}")
        parts.append(f"- Case Count: {report['case_count']}")
        parts.append("")
        parts.append("## Variants")
        parts.append("")
        for variant_report in report["variants"]:
            variant = variant_report["variant"]
            aggregate = variant_report["aggregate"]
            deltas = report["deltas"][variant["name"]]
            parts.append(f"### {variant['name']}")
            if variant.get("description"):
                parts.append(f"- Description: {variant['description']}")
            parts.append(f"- Settings Overrides: {variant.get('settings_overrides')}")
            parts.append(f"- Avg Retrieval Hit Rate: {aggregate['avg_retrieval_hit_rate']}")
            parts.append(f"- Avg Primary Score: {aggregate['avg_primary_score']}")
            parts.append(f"- Avg Retrieval Score: {aggregate['avg_retrieval_score']}")
            parts.append(f"- Validation Pass Rate: {aggregate['validation_pass_rate']}")
            parts.append(f"- Repair Success Rate: {aggregate['repair_success_rate']}")
            parts.append(f"- Delta vs Baseline: {deltas}")
            parts.append("")
        return "\n".join(parts)

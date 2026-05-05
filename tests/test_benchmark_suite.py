import json

from evaluation import BenchmarkCase, BenchmarkSuiteRunner, BenchmarkVariant
from config import settings


class _FakePlatform:
    def __init__(self, artifacts_root):
        self.artifacts_root = artifacts_root
        self.counter = 0

    def run(self, user_input, workspace_root, validate, mode, validation_mode, focus_file=None):
        self.counter += 1
        session_id = f"fake_{self.counter}"
        session_dir = self.artifacts_root / f"session_{session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)
        retrieval_payload = {
            "results": [
                {"relative_path": "main.go"},
                {"relative_path": "README.md"},
            ]
        }
        (session_dir / "03_retrieval_results.json").write_text(
            json.dumps(retrieval_payload, ensure_ascii=False),
            encoding="utf-8",
        )
        return {
            "session_id": session_id,
            "execution_mode": mode,
            "llm_config": {"provider": "fake", "model": "fake-model"},
            "llm_response": "main calculate bug readme",
            "evaluation_output": {
                "retrieval_hit_rate": 0.75,
                "primary_score": 0.8,
                "avg_retrieval_score": 0.72,
                "retrieved_code_ratio": 0.5,
                "validation_passed": False,
                "repair_success": False,
                "rag_backend": "hybrid",
                "lexical_backend": settings.LEXICAL_BACKEND,
                "rerank_enabled": settings.RERANK_ENABLED,
                "embedding_provider": "ollama",
            },
        }


def test_benchmark_suite_generates_report(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    settings.ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)

    fake_platform = _FakePlatform(settings.ARTIFACTS_ROOT)
    runner = BenchmarkSuiteRunner(
        platform_factory=lambda: fake_platform,
        output_root=tmp_path / "benchmark_reports",
    )
    cases = [
        BenchmarkCase(
            name="single_case",
            workspace_root="/tmp/workspace",
            query="分析 main.go",
            mode="single",
            expected_files=["main.go", "README.md"],
            expected_keywords=["main", "bug"],
        ),
        BenchmarkCase(
            name="multi_case",
            workspace_root="/tmp/workspace",
            query="分析 Calculate",
            mode="multi",
            expected_files=["main.go"],
            expected_keywords=["calculate"],
        ),
    ]

    report = runner.run_suite(cases=cases, validate=False, validation_mode="local")

    assert report["case_count"] == 2
    assert report["aggregate"]["cases"] == 2
    assert "single" in report["by_mode"]
    assert "multi" in report["by_mode"]
    assert report["cases"][0]["expectation_check"]["file_hit_rate"] == 1.0
    assert any((tmp_path / "benchmark_reports").glob("benchmark_*.json"))
    assert any((tmp_path / "benchmark_reports").glob("benchmark_*.md"))


def test_benchmark_suite_run_suite_accepts_settings_overrides(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    settings.ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)

    fake_platform = _FakePlatform(settings.ARTIFACTS_ROOT)
    runner = BenchmarkSuiteRunner(
        platform_factory=lambda: fake_platform,
        output_root=tmp_path / "benchmark_reports",
    )

    report = runner.run_suite(
        cases=[
            BenchmarkCase(
                name="single_case",
                workspace_root="/tmp/workspace",
                query="分析 main.go",
                mode="single",
            )
        ],
        validate=False,
        validation_mode="local",
        settings_overrides={"LEXICAL_BACKEND": "keyword", "RERANK_ENABLED": False},
    )

    assert report["cases"][0]["evaluation_output"]["lexical_backend"] == "keyword"
    assert report["cases"][0]["evaluation_output"]["rerank_enabled"] is False


def test_benchmark_suite_can_compare_variants(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ARTIFACTS_ROOT", tmp_path / "artifacts")
    settings.ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)

    fake_platform = _FakePlatform(settings.ARTIFACTS_ROOT)
    runner = BenchmarkSuiteRunner(
        platform_factory=lambda: fake_platform,
        output_root=tmp_path / "benchmark_reports",
    )
    variants = [
        BenchmarkVariant(
            name="baseline",
            settings_overrides={"LEXICAL_BACKEND": "keyword", "RERANK_ENABLED": False},
        ),
        BenchmarkVariant(
            name="bm25_rerank",
            settings_overrides={"LEXICAL_BACKEND": "bm25", "RERANK_ENABLED": True},
        ),
    ]

    report = runner.run_comparison(
        variants,
        cases=[
            BenchmarkCase(
                name="single_case",
                workspace_root="/tmp/workspace",
                query="分析 main.go",
                mode="single",
                expected_files=["main.go"],
                expected_keywords=["main"],
            )
        ],
        validate=False,
        validation_mode="local",
    )

    assert report["baseline_variant"] == "baseline"
    assert len(report["variants"]) == 2
    assert "bm25_rerank" in report["deltas"]
    assert any((tmp_path / "benchmark_reports").glob("benchmark_compare_*.json"))
    assert any((tmp_path / "benchmark_reports").glob("benchmark_compare_*.md"))

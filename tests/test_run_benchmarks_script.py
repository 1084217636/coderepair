import argparse
import importlib.util
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_benchmarks.py"
    spec = importlib.util.spec_from_file_location("run_benchmarks_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_variants_defaults_to_recommended_progression():
    module = _load_script_module()
    args = argparse.Namespace(
        variants=None,
        rag_backend="hybrid",
        bm25_k1=None,
        bm25_b=None,
        rerank_top_n=None,
    )

    variants = module.build_variants(args)

    assert [variant.name for variant in variants] == [
        "keyword_baseline",
        "bm25_only",
        "bm25_rerank",
    ]
    assert variants[0].settings_overrides["LEXICAL_BACKEND"] == "keyword"
    assert variants[2].settings_overrides["RERANK_ENABLED"] is True
    assert variants[0].settings_overrides["RAG_BACKEND"] == "hybrid"


def test_select_cases_can_limit_default_suite():
    module = _load_script_module()

    cases = module.select_cases(limit=2)

    assert len(cases) == 2


def test_select_cases_can_choose_go_repair_suite():
    module = _load_script_module()

    cases = module.select_cases(limit=3, suite_name="go-repair")

    assert len(cases) == 3
    assert cases[0].category == "compile_error"

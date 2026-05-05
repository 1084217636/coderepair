from retrieval.retriever import Retriever
from retrieval.reranker import EvidenceReranker


def test_bm25_lexical_backend_prefers_symbol_and_summary_hits(tmp_path):
    chunks = [
        {
            "relative_path": "service/user.go",
            "language": "go",
            "text": "package service\n\nfunc CreateUser() error {\n    return nil\n}\n",
            "start_line": 1,
            "end_line": 5,
            "summary": "func CreateUser() error",
            "chunk_kind": "function",
            "symbol": "CreateUser",
        },
        {
            "relative_path": "docs/README.md",
            "language": "markdown",
            "text": "This document explains how users are created in the system.",
            "start_line": 1,
            "end_line": 1,
            "summary": "Create user guide",
            "chunk_kind": "chunk",
            "symbol": "",
        },
    ]

    retriever = Retriever(
        chunks,
        top_k=1,
        workspace_root=tmp_path,
        backend="lexical",
        lexical_backend="bm25",
        rerank_enabled=False,
    )

    results = retriever.retrieve("请分析 CreateUser 的错误处理")

    assert retriever.get_backend_summary()["lexical_backend"] == "bm25"
    assert results[0]["relative_path"] == "service/user.go"
    assert results[0]["lexical_backend"] == "bm25"


def test_evidence_reranker_can_promote_exact_symbol_match():
    reranker = EvidenceReranker()
    results = [
        {
            "relative_path": "docs/README.md",
            "language": "markdown",
            "summary": "Create user overview",
            "symbol": "",
            "chunk_kind": "chunk",
            "score": 0.95,
        },
        {
            "relative_path": "service/user.go",
            "language": "go",
            "summary": "func CreateUser() error",
            "symbol": "CreateUser",
            "chunk_kind": "function",
            "score": 0.82,
        },
    ]

    reranked = reranker.rerank("修复 CreateUser 的返回值", results, top_n=2)

    assert reranked[0]["relative_path"] == "service/user.go"
    assert reranked[0]["rerank_score"] >= reranked[1]["rerank_score"]

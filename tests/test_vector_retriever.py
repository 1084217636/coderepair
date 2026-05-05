from pathlib import Path

from retrieval.retriever import Retriever


def test_vector_retriever_can_index_and_search(tmp_path):
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
            "relative_path": "server/http.go",
            "language": "go",
            "text": "package server\n\nfunc StartHTTPServer() error {\n    return nil\n}\n",
            "start_line": 1,
            "end_line": 5,
            "summary": "func StartHTTPServer() error",
            "chunk_kind": "function",
            "symbol": "StartHTTPServer",
        },
    ]

    retriever = Retriever(
        chunks,
        top_k=1,
        workspace_root=tmp_path,
        backend="vector",
        vector_db_path=tmp_path / "vectors.sqlite3",
        embedding_dim=128,
        vector_candidates=5,
    )

    results = retriever.retrieve("请分析 CreateUser 的实现")

    assert len(results) == 1
    assert results[0]["relative_path"] == "service/user.go"
    assert "vector_score" in results[0]
    assert results[0]["chunk_kind"] == "function"
    assert results[0]["symbol"] == "CreateUser"


def test_hybrid_retriever_merges_vector_and_lexical_scores(tmp_path):
    chunks = [
        {
            "relative_path": "pkg/auth.go",
            "language": "go",
            "text": "package pkg\n\nfunc ValidateToken() bool {\n    return true\n}\n",
            "start_line": 1,
            "end_line": 5,
            "summary": "func ValidateToken() bool",
            "chunk_kind": "function",
            "symbol": "ValidateToken",
        },
        {
            "relative_path": "pkg/cache.go",
            "language": "go",
            "text": "package pkg\n\nfunc WarmCache() {}\n",
            "start_line": 1,
            "end_line": 3,
            "summary": "func WarmCache()",
            "chunk_kind": "function",
            "symbol": "WarmCache",
        },
    ]

    retriever = Retriever(
        chunks,
        top_k=1,
        workspace_root=tmp_path,
        backend="hybrid",
        vector_db_path=tmp_path / "vectors.sqlite3",
        embedding_dim=128,
        vector_candidates=5,
    )

    results = retriever.retrieve("ValidateToken token 校验")

    assert len(results) == 1
    assert results[0]["relative_path"] == "pkg/auth.go"
    assert results[0]["retrieval_backend"] == "hybrid"

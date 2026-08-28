from deerflow.code_change.context_retriever import build_retrieval_context, retrieve_context, tokenize
from deerflow.code_change.repo_scanner import scan_repo


def test_scan_repo_skips_noise_and_retrieves_context(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "health.go").write_text('package main\nfunc Health() string { return "ok" }\n', encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / ".git" / "config").write_text("secret", encoding="utf-8")

    files = scan_repo(str(repo))
    contexts = retrieve_context(str(repo), "fix health endpoint", files)

    assert [item.path for item in files] == ["health.go"]
    assert contexts[0].path == "health.go"


def test_tokenize_keeps_identifiers_and_adds_chinese_ngrams():
    terms = tokenize("修复登录接口 login_handler")

    assert "login_handler" in terms
    assert "登录" in terms
    assert "接口" in terms


class FakeEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0] if "authentication" in text else [0.0, 1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "Bearer" in text else [0.0, 1.0] for text in texts]


def test_hybrid_retrieval_combines_symbol_and_semantic_signals(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.py").write_text(
        "class TokenVerifier:\n    def validate_bearer(self, header):\n        return header.startswith('Bearer ')\n",
        encoding="utf-8",
    )
    (repo / "math.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    files = scan_repo(str(repo))

    contexts = retrieve_context(
        str(repo),
        "authentication TokenVerifier",
        files,
        embedding_provider=FakeEmbeddings(),
        limit=3,
    )

    assert contexts[0].path == "auth.py"
    assert "TokenVerifier" in contexts[0].symbols
    assert contexts[0].symbol_score > 0
    assert contexts[0].semantic_score > 0
    assert "lexical=" in contexts[0].reason
    assert "symbol=" in contexts[0].reason
    assert "semantic=" in contexts[0].reason


def test_embedding_failure_falls_back_to_lexical_and_symbol(tmp_path):
    class BrokenEmbeddings:
        def embed_query(self, text: str) -> list[float]:
            raise RuntimeError("provider unavailable")

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("provider unavailable")

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "service.go").write_text(
        "package service\ntype HealthStore interface { Ping() error }\nfunc CheckHealth() error { return nil }\n",
        encoding="utf-8",
    )
    contexts = retrieve_context(
        str(repo),
        "CheckHealth HealthStore",
        scan_repo(str(repo)),
        embedding_provider=BrokenEmbeddings(),
    )

    assert contexts[0].path == "service.go"
    assert {"HealthStore", "CheckHealth"}.issubset(contexts[0].symbols)
    assert contexts[0].semantic_score == 0
    assert "semantic=unavailable" in contexts[0].reason


def test_retrieval_context_builder_obeys_token_budget(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for index in range(4):
        (repo / f"handler_{index}.py").write_text(
            f"def login_handler_{index}(request):\n" + "    # validate login request\n" * 100,
            encoding="utf-8",
        )
    contexts = retrieve_context(str(repo), "login handler validation", scan_repo(str(repo)), limit=8)

    bundle = build_retrieval_context(contexts, token_budget=300)

    assert bundle.estimated_tokens <= 300
    assert bundle.items
    assert bundle.truncated is True
    assert bundle.items[0].path in bundle.prompt

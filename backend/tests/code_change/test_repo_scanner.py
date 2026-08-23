from deerflow.code_change.context_retriever import retrieve_context, tokenize
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

import httpx

from retrieval.embeddings import create_embedder


def test_ollama_embedder_falls_back_to_hashing(monkeypatch):
    def fake_post(self, url, json):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    embedder = create_embedder(
        provider="ollama",
        dimension=32,
        ollama_model="embeddinggemma",
        ollama_api_base="http://localhost:11434",
        timeout=3,
    )

    vectors = embedder.embed_texts(["hello world"])
    summary = embedder.summary()

    assert len(vectors) == 1
    assert len(vectors[0]) == 32
    assert summary["provider"] == "hashing"
    assert summary["requested_provider"] == "ollama"
    assert summary["fallback_reason"]


def test_ollama_embedder_uses_remote_embeddings(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}

    def fake_post(self, url, json):
        assert url == "http://localhost:11434/api/embed"
        assert json["model"] == "embeddinggemma"
        return FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    embedder = create_embedder(
        provider="ollama",
        dimension=32,
        ollama_model="embeddinggemma",
        ollama_api_base="http://localhost:11434/v1",
        timeout=3,
    )

    vectors = embedder.embed_texts(["a", "b"])
    summary = embedder.summary()

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert summary["provider"] == "ollama"
    assert summary["embedding_dim"] == 3
    assert summary["semantic"] is True

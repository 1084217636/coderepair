from __future__ import annotations

import os
from typing import Protocol


class EmbeddingProvider(Protocol):
    """Minimal provider boundary used by the in-memory code index."""

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


def embedding_provider_from_env() -> EmbeddingProvider | None:
    """Build an OpenAI-compatible provider only when explicitly configured.

    No embedding configuration means lexical + symbol fallback. This keeps the
    default local demo usable without silently making paid network calls.
    """

    model = os.getenv("CODE_CHANGE_EMBEDDING_MODEL", "").strip()
    if not model:
        return None
    api_key = os.getenv("CODE_CHANGE_EMBEDDING_API_KEY", "").strip()
    base_url = os.getenv("CODE_CHANGE_EMBEDDING_BASE_URL", "").strip()
    if not api_key:
        raise ValueError("CODE_CHANGE_EMBEDDING_API_KEY is required when an embedding model is configured")

    from langchain_openai import OpenAIEmbeddings

    options: dict[str, object] = {"model": model, "api_key": api_key}
    if base_url:
        options["base_url"] = base_url
    dimensions = os.getenv("CODE_CHANGE_EMBEDDING_DIMENSIONS", "").strip()
    if dimensions:
        options["dimensions"] = int(dimensions)
    return OpenAIEmbeddings(**options)

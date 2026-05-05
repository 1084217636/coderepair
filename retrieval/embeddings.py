"""
嵌入模块

当前支持两类嵌入：
1. Ollama 本地语义 embedding（推荐）
2. 纯 Python hashing embedding（兜底）
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable, List, Optional

import httpx

from core.logger import get_logger

logger = get_logger(__name__)


class HashingEmbedder:
    """基于稳定哈希的轻量文本嵌入器。"""

    provider = "hashing"
    semantic = False

    def __init__(self, dimension: int = 384):
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.dimension = dimension
        self.model = "hashing_v1"
        self.fallback_reason: Optional[str] = None

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text.lower())

    def embed_text(self, text: str) -> List[float]:
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.dimension

        vector = [0.0] * self.dimension
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + min(len(token), 16) / 16.0
            vector[bucket] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        return [self.embed_text(text) for text in texts]

    def summary(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "embedding_dim": self.dimension,
            "semantic": self.semantic,
            "fallback_reason": self.fallback_reason,
        }


class OllamaEmbedder:
    """基于 Ollama 本地接口的语义 embedding。"""

    provider = "ollama"
    semantic = True

    def __init__(
        self,
        model: str,
        api_base: str,
        timeout: int = 30,
        fallback_embedder: Optional[HashingEmbedder] = None,
    ):
        self.model = model
        self.timeout = timeout
        self.dimension: int = 0
        self.fallback_embedder = fallback_embedder
        self.fallback_reason: Optional[str] = None
        self.api_base = self._normalize_api_base(api_base)

    @staticmethod
    def _normalize_api_base(api_base: str) -> str:
        base = api_base.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        return base

    def embed_text(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        payload = {
            "model": self.model,
            "input": list(texts),
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.api_base}/api/embed", json=payload)
                response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings") or []
            if not embeddings:
                raise RuntimeError("ollama embeddings response missing 'embeddings'")
            self.dimension = len(embeddings[0])
            self.fallback_reason = None
            return embeddings
        except Exception as e:
            if not self.fallback_embedder:
                raise
            self.fallback_reason = str(e)
            logger.warning(f"[Embeddings] Ollama embedding 不可用，回退 hashing | error={e}")
            fallback_vectors = self.fallback_embedder.embed_texts(payload["input"])
            self.dimension = self.fallback_embedder.dimension
            return fallback_vectors

    def summary(self) -> dict:
        using_fallback = self.fallback_reason is not None and self.fallback_embedder is not None
        if using_fallback:
            return {
                "provider": self.fallback_embedder.provider,
                "model": self.fallback_embedder.model,
                "embedding_dim": self.fallback_embedder.dimension,
                "semantic": False,
                "fallback_reason": self.fallback_reason,
                "requested_provider": self.provider,
                "requested_model": self.model,
            }
        return {
            "provider": self.provider,
            "model": self.model,
            "embedding_dim": self.dimension,
            "semantic": self.semantic,
            "fallback_reason": None,
        }


def create_embedder(
    provider: str,
    dimension: int,
    ollama_model: str,
    ollama_api_base: str,
    timeout: int = 30,
) -> HashingEmbedder | OllamaEmbedder:
    provider = provider.lower()
    if provider == "ollama":
        return OllamaEmbedder(
            model=ollama_model,
            api_base=ollama_api_base,
            timeout=timeout,
            fallback_embedder=HashingEmbedder(dimension=dimension),
        )
    return HashingEmbedder(dimension=dimension)

"""Embedding providers used for semantic matching."""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

VECTOR_SIZE = 64


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic bag-of-tokens embedder for tests and offline defaults."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        from app.matching.scoring import tokenize

        vectors: list[list[float]] = []
        for text in texts:
            counts = [0.0] * VECTOR_SIZE
            for token in tokenize(text):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:2], "big") % VECTOR_SIZE
                counts[index] += 1.0
            norm = math.sqrt(sum(v * v for v in counts))
            if norm:
                counts = [v / norm for v in counts]
            vectors.append(counts)
        return vectors


class AzureOpenAIEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        from app.ai.openai_client import get_openai_client
        from app.config import get_settings

        settings = get_settings()
        client = get_openai_client()
        response = client.embeddings.create(
            model=settings.azure_openai_embeddings_deployment,
            input=texts,
        )
        return [list(item.embedding) for item in response.data]


def default_embedder() -> Embedder:
    from app.config import get_settings

    settings = get_settings()
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        return AzureOpenAIEmbedder()
    return HashEmbedder()

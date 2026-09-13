"""Prime the embedding cache for hot job/resume endpoints."""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from app.matching.embedder import HashEmbedder


class EmbeddingCache:
    def __init__(self, *, max_items: int = 256, embedder: HashEmbedder | None = None) -> None:
        self.max_items = max_items
        self.embedder = embedder or HashEmbedder()
        self._store: OrderedDict[str, list[float]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def _put(self, key: str, vector: list[float]) -> None:
        self._store[key] = vector
        self._store.move_to_end(key)
        while len(self._store) > self.max_items:
            self._store.popitem(last=False)

    def get(self, text: str) -> list[float]:
        if text in self._store:
            self.hits += 1
            self._store.move_to_end(text)
            return self._store[text]
        self.misses += 1
        vector = self.embedder.embed([text])[0]
        self._put(text, vector)
        return vector

    def prime(self, texts: Iterable[str]) -> int:
        count = 0
        for text in texts:
            if text not in self._store:
                self.get(text)
                count += 1
        return count

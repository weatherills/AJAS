"""Tombstone deleted vectors and compact (vacuum) the live set."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VectorStore:
    live: dict[str, list[float]] = field(default_factory=dict)
    tombstones: set[str] = field(default_factory=set)

    def upsert(self, doc_id: str, vector: list[float]) -> None:
        self.tombstones.discard(doc_id)
        self.live[doc_id] = list(vector)

    def delete(self, doc_id: str) -> None:
        self.live.pop(doc_id, None)
        self.tombstones.add(doc_id)

    def get(self, doc_id: str) -> list[float] | None:
        if doc_id in self.tombstones:
            return None
        return self.live.get(doc_id)

    def vacuum(self) -> dict[str, int]:
        removed = 0
        for doc_id in list(self.live):
            if doc_id in self.tombstones:
                del self.live[doc_id]
                removed += 1
        kept_tombstones = len(self.tombstones)
        return {"live": len(self.live), "tombstones": kept_tombstones, "removed": removed}

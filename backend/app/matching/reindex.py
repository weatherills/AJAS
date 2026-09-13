"""Incremental embedding reindex sweeper with a bounded retry queue."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable

EmbedFn = Callable[[list[str]], list[list[float]]]


@dataclass
class ReindexItem:
    doc_id: str
    text: str
    attempts: int = 0
    last_error: str | None = None


@dataclass
class ReindexSweeper:
    embed: EmbedFn
    max_attempts: int = 3
    pending: deque[ReindexItem] = field(default_factory=deque)
    indexed: dict[str, list[float]] = field(default_factory=dict)
    dead: list[ReindexItem] = field(default_factory=list)

    def enqueue(self, doc_id: str, text: str) -> None:
        self.pending.append(ReindexItem(doc_id=doc_id, text=text))

    def sweep(self, *, limit: int = 50) -> dict[str, int]:
        processed = 0
        retried = 0
        failed = 0
        while self.pending and processed < limit:
            item = self.pending.popleft()
            processed += 1
            try:
                vector = self.embed([item.text])[0]
                self.indexed[item.doc_id] = vector
            except Exception as exc:  # noqa: BLE001 - retry queue must swallow provider errors
                item.attempts += 1
                item.last_error = str(exc)
                if item.attempts >= self.max_attempts:
                    self.dead.append(item)
                    failed += 1
                else:
                    self.pending.append(item)
                    retried += 1
        return {
            "processed": processed,
            "indexed": len(self.indexed),
            "retried": retried,
            "dead": failed,
            "pending": len(self.pending),
        }

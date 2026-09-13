"""Active-learning hooks: queue uncertain matches for retraining."""

from __future__ import annotations

from typing import Any

_QUEUE: list[dict[str, Any]] = []


def uncertain(score: float, *, low: float = 45.0, high: float = 70.0) -> bool:
    return low <= float(score) <= high


def enqueue(item: dict[str, Any], *, score: float) -> dict[str, Any] | None:
    if not uncertain(score):
        return None
    row = {**item, "score": score, "reason": "uncertain"}
    _QUEUE.append(row)
    return row


def drain(limit: int = 50) -> list[dict[str, Any]]:
    batch = _QUEUE[:limit]
    del _QUEUE[:limit]
    return batch


def snapshot() -> dict[str, int]:
    return {"queued": len(_QUEUE)}

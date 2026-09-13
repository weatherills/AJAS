"""Match result cache, async embedding writes with backpressure, index review."""

from __future__ import annotations

from collections import deque
from typing import Any, Callable

from app.db_indices import index_policy
from app.query_cache import get_item, reset as reset_cache, set_item

_QUEUE: deque[dict[str, Any]] = deque()
_WRITTEN: list[list[dict[str, Any]]] = []


def reset() -> None:
    reset_cache()
    _QUEUE.clear()
    _WRITTEN.clear()


def cached_matches(key: str, factory: Callable[[], list[dict[str, Any]]], *, ttl_sec: float = 20, now: float | None = None) -> list[dict[str, Any]]:
    hit = get_item(key, now=now)
    if hit is not None:
        return hit
    value = factory()
    set_item(key, value, ttl_sec=ttl_sec, now=now)
    return value


def invalidate(key: str) -> None:
    set_item(key, None, ttl_sec=0, now=0)


def enqueue_embeddings(items: list[dict[str, Any]], *, max_depth: int = 100) -> dict[str, Any]:
    accepted = 0
    dropped = 0
    for item in items:
        if len(_QUEUE) >= max_depth:
            dropped += 1
            continue
        _QUEUE.append(item)
        accepted += 1
    return {"accepted": accepted, "dropped": dropped, "depth": len(_QUEUE), "backpressure": dropped > 0}


def flush_embeddings(*, batch_size: int = 16) -> dict[str, Any]:
    flushed = 0
    while _QUEUE:
        batch = [ _QUEUE.popleft() for _ in range(min(batch_size, len(_QUEUE))) ]
        _WRITTEN.append(batch)
        flushed += len(batch)
    return {"flushed": flushed, "batches": len(_WRITTEN)}


def suggested_indices() -> dict[str, object]:
    policy = index_policy()
    extra = [{"path": "/tenantId", "order": "ascending"}, {"path": "/updatedAt", "order": "descending"}]
    included = list(policy["includedPaths"]) + extra
    return {**policy, "includedPaths": included, "reviewedAt": "sprint12"}

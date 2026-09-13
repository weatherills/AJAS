"""Query TTL cache for hot jobs/matches lists."""

from __future__ import annotations

from time import time
from typing import Any

_CACHE: dict[str, tuple[float, Any]] = {}


def reset() -> None:
    _CACHE.clear()


def set_item(key: str, value: Any, *, ttl_sec: float = 30, now: float | None = None) -> None:
    clock = now if now is not None else time()
    _CACHE[key] = (clock + ttl_sec, value)


def get_item(key: str, *, now: float | None = None) -> Any | None:
    clock = now if now is not None else time()
    row = _CACHE.get(key)
    if not row:
        return None
    expires, value = row
    if clock >= expires:
        _CACHE.pop(key, None)
        return None
    return value


def get_or_set(key: str, factory, *, ttl_sec: float = 30, now: float | None = None) -> Any:
    hit = get_item(key, now=now)
    if hit is not None:
        return hit
    value = factory()
    set_item(key, value, ttl_sec=ttl_sec, now=now)
    return value

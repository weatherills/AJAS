"""Per-tenant and per-endpoint rate counters."""

from __future__ import annotations

import time
from collections import defaultdict

_counts: dict[tuple[str, str], list[float]] = defaultdict(list)


def reset() -> None:
    _counts.clear()


def hit(tenant: str, endpoint: str, *, window_sec: float = 60.0, limit: int = 60, now: float | None = None) -> dict[str, object]:
    clock = now if now is not None else time.monotonic()
    key = ((tenant or "anon").strip(), (endpoint or "*").strip())
    stamps = [ts for ts in _counts[key] if clock - ts < window_sec]
    stamps.append(clock)
    _counts[key] = stamps
    remaining = max(0, limit - len(stamps))
    return {
        "tenant": key[0],
        "endpoint": key[1],
        "count": len(stamps),
        "limit": limit,
        "remaining": remaining,
        "allowed": len(stamps) <= limit,
    }

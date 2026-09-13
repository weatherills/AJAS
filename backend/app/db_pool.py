"""Connection pool size autotune from recent latency."""

from __future__ import annotations

from typing import Any


def autotune(*, latency_ms: float, current: int, min_size: int = 2, max_size: int = 32) -> dict[str, Any]:
    size = max(min_size, min(max_size, int(current)))
    if latency_ms > 250 and size < max_size:
        size = min(max_size, size + 2)
        action = "grow"
    elif latency_ms < 40 and size > min_size:
        size = max(min_size, size - 1)
        action = "shrink"
    else:
        action = "hold"
    return {"size": size, "action": action, "latencyMs": latency_ms}

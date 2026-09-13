"""Adaptive queue backpressure from depth."""

from __future__ import annotations

from typing import Any


def backpressure(depth: int, *, soft: int = 100, hard: int = 500) -> dict[str, Any]:
    queued = max(0, int(depth))
    if queued >= hard:
        delay_ms = 30_000
        mode = "shed"
    elif queued >= soft:
        delay_ms = min(15_000, 50 * (queued - soft + 1))
        mode = "slow"
    else:
        delay_ms = 0
        mode = "open"
    return {"depth": queued, "mode": mode, "delayMs": delay_ms, "admit": mode != "shed"}

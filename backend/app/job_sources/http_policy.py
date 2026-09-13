"""Rotating user agents and jittered retries for optional board HTTP."""

from __future__ import annotations

import hashlib
import random

USER_AGENTS = (
    "AJASJobIngest/1.0",
    "AJASJobIngest/1.0 (+https://ajas.local/ops)",
    "AJASJobIngest/1.1",
)


def rotate_user_agent(seed: str | None = None, *, index: int | None = None) -> str:
    if index is not None:
        return USER_AGENTS[index % len(USER_AGENTS)]
    if seed:
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return USER_AGENTS[digest[0] % len(USER_AGENTS)]
    return random.choice(USER_AGENTS)


def jittered_backoff(attempt: int, *, base: float = 0.25, cap: float = 8.0, jitter: float = 0.3) -> float:
    from app.job_sources.boards import backoff_seconds

    delay = backoff_seconds(attempt, base=base, cap=cap)
    if jitter <= 0:
        return delay
    spread = delay * jitter
    return max(0.0, min(cap, delay + random.uniform(-spread, spread)))

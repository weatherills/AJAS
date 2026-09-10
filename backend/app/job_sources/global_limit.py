"""Process-wide crawl rate limit (in addition to per-tenant buckets)."""

from __future__ import annotations

import time

from app.job_sources.errors import JobSourceRateLimitedError

GLOBAL_PER_MIN = 120
_tokens = float(GLOBAL_PER_MIN)
_updated = time.monotonic()


def consume_global(*, cost: float = 1.0) -> dict:
    global _tokens, _updated
    now = time.monotonic()
    elapsed = max(0.0, now - _updated)
    _tokens = min(float(GLOBAL_PER_MIN), _tokens + (GLOBAL_PER_MIN / 60.0) * elapsed)
    _updated = now
    if _tokens < cost:
        raise JobSourceRateLimitedError("global crawl rate limit")
    _tokens -= cost
    return {"limit": GLOBAL_PER_MIN, "remaining": int(_tokens)}


def snapshot() -> dict:
    return {"limitPerMin": GLOBAL_PER_MIN, "tokensRemaining": round(_tokens, 2)}

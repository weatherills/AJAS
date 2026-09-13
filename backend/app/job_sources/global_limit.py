"""Process-wide crawl rate limit (in addition to per-tenant buckets)."""

from __future__ import annotations

import time

from app.job_sources.errors import JobSourceRateLimitedError

GLOBAL_PER_MIN = 120
DAILY_CAP = 10_000
_tokens = float(GLOBAL_PER_MIN)
_updated = time.monotonic()
_day_count = 0
_day_stamp = ""


def consume_global(*, cost: float = 1.0) -> dict:
    global _tokens, _updated, _day_count, _day_stamp
    now = time.monotonic()
    elapsed = max(0.0, now - _updated)
    _tokens = min(float(GLOBAL_PER_MIN), _tokens + (GLOBAL_PER_MIN / 60.0) * elapsed)
    _updated = now
    day = time.strftime("%Y-%m-%d", time.gmtime())
    if _day_stamp != day:
        _day_stamp = day
        _day_count = 0
    if _day_count + cost > DAILY_CAP:
        raise JobSourceRateLimitedError("daily source quota exceeded")
    if _tokens < cost:
        raise JobSourceRateLimitedError("global crawl rate limit")
    _tokens -= cost
    _day_count += int(cost)
    return {"limit": GLOBAL_PER_MIN, "remaining": int(_tokens), "dailyRemaining": DAILY_CAP - _day_count}


def snapshot() -> dict:
    return {
        "limitPerMin": GLOBAL_PER_MIN,
        "tokensRemaining": round(_tokens, 2),
        "dailyCap": DAILY_CAP,
        "dailyUsed": _day_count,
    }

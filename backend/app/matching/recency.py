"""Recency / time-decay factor for match ranking."""

from __future__ import annotations

from datetime import datetime, timezone
from math import exp


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    text = stamp.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_days(posted_at: str | None, *, now: datetime | None = None) -> float | None:
    parsed = _parse(posted_at)
    if parsed is None:
        return None
    clock = now or datetime.now(timezone.utc)
    return max(0.0, (clock - parsed).total_seconds() / 86400.0)


def recency_boost(posted_at: str | None, *, now: datetime | None = None, half_life_days: float = 14.0) -> float:
    """Return an additive 0–6 boost that decays with posting age."""
    days = age_days(posted_at, now=now)
    if days is None:
        return 0.0
    if half_life_days <= 0:
        return 0.0
    decay = exp(-days / half_life_days)
    return round(6.0 * decay, 2)

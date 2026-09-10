"""Ids, timestamps, and score helpers for Learning Loop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4


def new_id() -> str:
    return str(uuid4())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(value: str):
    stamp = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def hours_ago(hours: float, *, now: str | None = None) -> str:
    stamp = parse_ts(now or utc_now()) - timedelta(hours=hours)
    return stamp.isoformat().replace("+00:00", "Z")


def days_ago(days: float, *, now: str | None = None) -> str:
    return hours_ago(days * 24, now=now)


def clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def as_unit_score(value: float) -> float:
    """Accept 0–1 or 0–100 display scores."""
    raw = float(value)
    if raw > 1.0:
        raw = raw / 100.0
    return clamp_unit(raw)


def period_start(period: str, *, now: str | None = None):
    days = 30 if period == "30d" else 7
    return parse_ts(now or utc_now()) - timedelta(days=days)

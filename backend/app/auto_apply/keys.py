"""Timestamps for Auto-Apply documents."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(value: str):
    stamp = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def plus_days(days: int, *, now: str | None = None) -> str:
    start = parse_ts(now or utc_now())
    return (start + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def is_expired(expires_at: str | None, *, now: str | None = None) -> bool:
    if not expires_at:
        return False
    return parse_ts(expires_at) <= parse_ts(now or utc_now())

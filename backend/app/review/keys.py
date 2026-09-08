"""Timestamps and etags for Review documents."""

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


def is_lock_expired(expires_at: str | None, *, now: str | None = None) -> bool:
    if not expires_at:
        return True
    return parse_ts(expires_at) <= parse_ts(now or utc_now())


def lock_until(seconds: int, *, now: str | None = None) -> str:
    start = parse_ts(now or utc_now())
    return (start + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def next_etag(current: str | None) -> str:
    try:
        return str(int(current or "0") + 1)
    except (TypeError, ValueError):
        return "1"

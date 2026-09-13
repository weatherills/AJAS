"""Snooze / until-date follow-ups with weekday business-hours awareness."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.mail.sla import _parse

BUSINESS_START = 9
BUSINESS_END = 17


def _next_business(dt: datetime) -> datetime:
    cursor = dt
    for _ in range(14):
        if cursor.weekday() >= 5:
            cursor = (cursor + timedelta(days=1)).replace(
                hour=BUSINESS_START, minute=0, second=0, microsecond=0
            )
            continue
        if cursor.hour < BUSINESS_START:
            return cursor.replace(hour=BUSINESS_START, minute=0, second=0, microsecond=0)
        if cursor.hour >= BUSINESS_END:
            cursor = (cursor + timedelta(days=1)).replace(
                hour=BUSINESS_START, minute=0, second=0, microsecond=0
            )
            continue
        return cursor.replace(microsecond=0)
    return cursor.replace(microsecond=0)


def snooze_until(
    *,
    now: datetime | str | None = None,
    until: datetime | str | None = None,
    hours: int | None = None,
    business_hours: bool = True,
) -> dict[str, Any]:
    clock = _parse(now) or datetime.now(timezone.utc)
    target = _parse(until)
    if target is None:
        target = clock + timedelta(hours=int(hours or 24))
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    adjusted = _next_business(target.astimezone(timezone.utc)) if business_hours else target.replace(microsecond=0)
    return {
        "until": adjusted.isoformat().replace("+00:00", "Z"),
        "businessHours": business_hours,
        "rolled": adjusted != target.replace(microsecond=0),
    }

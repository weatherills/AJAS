"""Auto-reminders for unreplied threads at 24h and 72h SLAs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

SLA_HOURS = (24, 72)


def _parse(stamp: str | datetime | None) -> datetime | None:
    if stamp is None:
        return None
    if isinstance(stamp, datetime):
        parsed = stamp
    else:
        try:
            parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def followup_reminders(
    *,
    last_inbound_at: str | datetime | None,
    last_outbound_at: str | datetime | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    clock = now or datetime.now(timezone.utc)
    inbound = _parse(last_inbound_at)
    outbound = _parse(last_outbound_at)
    if inbound is None:
        return {"due": [], "replied": False, "hoursOpen": None}
    if outbound and outbound >= inbound:
        return {"due": [], "replied": True, "hoursOpen": round((outbound - inbound).total_seconds() / 3600, 2)}
    hours_open = (clock - inbound).total_seconds() / 3600
    due = [hour for hour in SLA_HOURS if hours_open >= hour]
    next_at = None
    pending = [hour for hour in SLA_HOURS if hours_open < hour]
    if pending:
        next_at = (inbound + timedelta(hours=pending[0])).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "due": due,
        "replied": False,
        "hoursOpen": round(hours_open, 2),
        "nextAt": next_at,
        "remind": bool(due),
    }

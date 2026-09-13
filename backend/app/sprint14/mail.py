"""Sprint 14 mail: IMAP labels, sender warmup, reply previews, follow-ups."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.flags import feature_enabled
from app.sprint13.product import followup_window, reply_plan

_SENDS: dict[str, int] = {}
_LABELS = {"INBOX": "new", "Interview": "interview", "Reject": "reject", "Offer": "offer"}


def reset() -> None:
    _SENDS.clear()


def imap_label(folder: str) -> dict[str, Any]:
    return {"folder": folder, "state": _LABELS.get(folder, "other"), "imap": feature_enabled("imap_transport")}


def sender_guard(sender: str, *, sent_today: int, warmup_cap: int = 20) -> dict[str, Any]:
    used = _SENDS.get(sender, sent_today)
    _SENDS[sender] = used
    return {"sender": sender, "allow": used < warmup_cap, "cap": warmup_cap, "used": used}


def reply_preview(*, intent: str, role: str, tone: str = "professional") -> dict[str, Any]:
    plan = reply_plan(intent=intent, tone=tone)
    body = plan["body"].replace("{{role}}", role).replace("{{slot}}", "Tue 10:00")
    return {**plan, "preview": body, "placeholders": ["role", "slot"]}


def reminder_slots(now: datetime | None = None) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    first = clock + timedelta(hours=24)
    second = clock + timedelta(hours=72)
    return {
        "h24": first.isoformat(),
        "h72": second.isoformat(),
        "send24": True,
        "window": followup_window(weekday=first.weekday(), hour=first.hour),
    }

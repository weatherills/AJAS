"""Sprint 15 mail: threads, bounces, quiet hours, suppression."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.flags import feature_enabled
from app.sprint14.mail import reminder_slots, reply_preview, sender_guard


def reset() -> None:
    return None


def merge_threads(messages: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in messages:
        key = str(row.get("messageId") or row.get("id") or "")
        groups.setdefault(key, []).append(row)
    return {"threads": groups, "count": len(groups)}


def bounce_v2(text: str) -> str:
    lowered = (text or "").lower()
    if "complaint" in lowered or "spam" in lowered:
        return "complaint"
    if "bounce" in lowered or "undeliver" in lowered:
        return "bounce"
    return "ok"


def calendar_placeholder(*, intent: str, role: str) -> dict[str, Any]:
    row = reply_preview(intent=intent, role=role)
    return {**row, "calendar": "https://cal.example.test/ada", "placeholders": [*row.get("placeholders", []), "calendar"]}


def skip_if_replied(*, replied: bool) -> dict[str, Any]:
    slots = reminder_slots()
    return {**slots, "skip": replied, "send24": slots["send24"] and not replied}


def quiet_hours(*, hour: int, start: int = 21, end: int = 8) -> bool:
    if start > end:
        return hour >= start or hour < end
    return start <= hour < end


def channel_prefs(*, user_id: str, email: bool = True, toast: bool = True) -> dict[str, Any]:
    return {"userId": user_id, "email": email, "toast": toast}


def inbox_split(sender: str) -> str:
    lowered = (sender or "").lower()
    if "greenhouse" in lowered or "lever" in lowered or "workday" in lowered:
        return "ats"
    return "recruiter"


def ab_subject(control: str, variant: str, *, pick: str = "control") -> dict[str, Any]:
    return {"control": control, "variant": variant, "chosen": control if pick == "control" else variant}


def signature(*, name: str, title: str) -> str:
    return f"{name}\n{title}\nAJAS"


def suppression_sync(emails: list[str], blocked: set[str]) -> dict[str, Any]:
    dropped = [item for item in emails if item.lower() in {b.lower() for b in blocked}]
    kept = [item for item in emails if item not in dropped]
    return {"kept": kept, "dropped": dropped, "imap": feature_enabled("imap_transport")}


def warmup(sender: str, *, sent_today: int) -> dict[str, Any]:
    return sender_guard(sender, sent_today=sent_today)

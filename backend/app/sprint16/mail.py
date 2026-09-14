"""Sprint 16 mail: In-Reply-To threads, auto-replies, quiet weekends, List-Unsubscribe."""

from __future__ import annotations

from typing import Any

from app.flags import feature_enabled
from app.sprint15.mail import bounce_v2, quiet_hours, reminder_slots, reply_preview, sender_guard


def reset() -> None:
    return None


def merge_in_reply_to(messages: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in messages:
        key = str(row.get("inReplyTo") or row.get("messageId") or row.get("id") or "")
        groups.setdefault(key, []).append(row)
    return {"threads": groups, "count": len(groups), "schema": "ajas.mail.irt"}


def auto_reply(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    hit = "out of office" in lowered or "auto-reply" in lowered or "autoreply" in lowered
    kind = bounce_v2(text)
    return {"auto": hit, "kind": kind if not hit else "auto"}


def calendar_tz(*, intent: str, role: str, tz: str = "UTC") -> dict[str, Any]:
    row = reply_preview(intent=intent, role=role)
    return {**row, "tz": tz, "calendar": "https://cal.example.test/ada", "placeholders": [*row.get("placeholders", []), "calendar", "tz"]}


def skip_if_meeting(*, replied: bool, meeting: bool) -> dict[str, Any]:
    slots = reminder_slots()
    skip = replied or meeting
    return {**slots, "skip": skip, "send24": slots["send24"] and not skip, "meeting": meeting}


def weekend_quiet(*, weekday: str, hour: int) -> bool:
    if weekday.lower()[:3] in {"sat", "sun"}:
        return True
    return quiet_hours(hour=hour)


def digest_vs_instant(*, instant: bool) -> str:
    return "instant" if instant else "digest"


def inbox_split_v2(sender: str) -> str:
    lowered = (sender or "").lower()
    if any(token in lowered for token in ("greenhouse", "lever", "workday", "icims", "taleo", "smartrecruiters")):
        return "ats"
    return "human"


def ab_body(control: str, variant: str, *, pick: str = "control") -> dict[str, Any]:
    return {"control": control, "variant": variant, "chosen": control if pick == "control" else variant, "kind": "body"}


def legal_disclaimer(*, name: str, title: str) -> str:
    return f"{name}\n{title}\nAJAS\nThis message is confidential."


def list_unsubscribe(emails: list[str], blocked: set[str], *, header: str | None = None) -> dict[str, Any]:
    extra = set()
    if header:
        extra.add(header.lower())
    blocked_l = {b.lower() for b in blocked} | extra
    dropped = [item for item in emails if item.lower() in blocked_l]
    kept = [item for item in emails if item not in dropped]
    return {"kept": kept, "dropped": dropped, "honored": bool(header), "imap": feature_enabled("imap_transport")}


def warmup(sender: str, *, sent_today: int) -> dict[str, Any]:
    return sender_guard(sender, sent_today=sent_today)

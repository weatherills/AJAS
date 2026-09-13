"""Saved-search alerts, triage chips, virtualization, follow-up, replies, profiles, mobile nav."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.matching.keys import utc_now

_ALERTS: list[dict[str, Any]] = []
_PROFILES: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _ALERTS.clear()
    _PROFILES.clear()


def keyword_alert(*, user_id: str, query: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    row = {"id": str(uuid4()), "userId": user_id, "query": query, "hits": hits, "channel": "email", "at": utc_now()}
    _ALERTS.append(row)
    return row


def refresh_saved_search(*, stale_after_min: int, age_min: int) -> dict[str, Any]:
    refresh = age_min >= stale_after_min
    return {"refresh": refresh, "notify": refresh}


def explanation_chips(reasons: list[str]) -> list[dict[str, str]]:
    return [{"label": item, "detail": f"Matched on {item}"} for item in reasons]


def jd_diff_blocks(old: str, new: str) -> dict[str, Any]:
    from app.job_sources.diff import diff_job_description

    raw = diff_job_description(old, new)
    return {**raw, "visualization": "split", "changed": bool(raw.get("changed") or raw.get("added") or raw.get("removed"))}


def virtual_window(n: int, *, start: int, height: int = 20) -> dict[str, Any]:
    end = min(n, start + height)
    return {"start": start, "end": end, "ids": list(range(start, end)), "virtualized": n > height}


def followup_window(*, weekday: int, hour: int) -> dict[str, Any]:
    # Mon=0 ... Sun=6, prefer Tue-Thu 9-16 local
    good_day = weekday in {1, 2, 3}
    good_hour = 9 <= hour < 16
    return {"send": good_day and good_hour, "weekday": weekday, "hour": hour}


def reply_plan(*, intent: str, tone: str = "professional") -> dict[str, Any]:
    templates = {
        "interview": "Thanks for the invite — I can do {{slot}}.",
        "reject": "Thank you for the update. I appreciate the time.",
        "followup": "Just checking in on {{role}}.",
    }
    return {"intent": intent, "tone": tone, "body": templates.get(intent, "Thanks for reaching out."), "controls": ["professional", "warm", "concise"]}


def save_profile(*, user_id: str, name: str, role_type: str) -> dict[str, Any]:
    row = {"id": str(uuid4()), "userId": user_id, "name": name, "roleType": role_type, "active": False}
    _PROFILES[row["id"]] = row
    return row


def switch_profile(profile_id: str, *, user_id: str) -> dict[str, Any]:
    row = _PROFILES.get(profile_id)
    if not row:
        raise KeyError("profile")
    if row["userId"] != user_id:
        raise PermissionError("profile")
    for item in _PROFILES.values():
        if item["userId"] == user_id:
            item["active"] = item["id"] == profile_id
    return row


def bottom_nav() -> list[dict[str, str]]:
    return [
        {"href": "#/jobs", "label": "Jobs"},
        {"href": "#/review", "label": "Review"},
        {"href": "#/apply", "label": "Apply"},
        {"href": "#/email", "label": "Mail"},
        {"href": "#/settings", "label": "More"},
    ]


def next_followup_slot(now: datetime | None = None) -> datetime:
    clock = now or datetime.now(timezone.utc)
    probe = clock.replace(minute=0, second=0, microsecond=0)
    for _ in range(24 * 7):
        if followup_window(weekday=probe.weekday(), hour=probe.hour)["send"]:
            return probe if probe >= clock else probe + timedelta(hours=1)
        probe += timedelta(hours=1)
    return clock + timedelta(hours=24)

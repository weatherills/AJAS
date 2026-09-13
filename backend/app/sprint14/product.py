"""Sprint 14 product helpers: search, apply, notifications, a11y, i18n."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.sprint13.ops import audit_bundle
from app.sprint13.platform import api_query, seed_v3
from app.sprint13.product import explanation_chips, jd_diff_blocks, refresh_saved_search, virtual_window

_PRESETS: dict[str, list[dict[str, Any]]] = {}
_PROFILES: dict[str, dict[str, Any]] = {}
_TOASTS: list[dict[str, Any]] = []


def reset() -> None:
    _PRESETS.clear()
    _PROFILES.clear()
    _TOASTS.clear()


def save_preset(*, user_id: str, name: str, filters: dict[str, Any]) -> dict[str, Any]:
    row = {"id": str(uuid4()), "name": name, "filters": filters, "userId": user_id}
    _PRESETS.setdefault(user_id, []).append(row)
    return row


def list_presets(user_id: str) -> list[dict[str, Any]]:
    return list(_PRESETS.get(user_id) or [])


def search_jd(items: list[dict[str, Any]], q: str) -> dict[str, Any]:
    return api_query(items, q=q, sort="id")


def windowed(n: int, *, start: int = 0) -> dict[str, Any]:
    return virtual_window(n, start=start, height=20)


def jd_diff(old: str, new: str) -> dict[str, Any]:
    return jd_diff_blocks(old, new)


def bulk_dismiss(ids: list[str], selected: list[str]) -> dict[str, Any]:
    dismissed = [item for item in selected if item in ids]
    remaining = [item for item in ids if item not in dismissed]
    return {"dismissed": dismissed, "remaining": remaining, "undo": dismissed}


def field_map(*, site: str, fields: dict[str, str]) -> dict[str, Any]:
    return {"site": site, "fields": fields, "overrides": True}


def cover_tone(text: str, *, tone: str = "professional") -> dict[str, Any]:
    prefix = {"warm": "I'd love to", "concise": "Applying for", "professional": "I am writing to apply for"}
    return {"tone": tone, "body": f"{prefix.get(tone, prefix['professional'])} {text}".strip(), "presets": list(prefix)}


def attach_profile(*, user_id: str, resume_id: str, name: str) -> dict[str, Any]:
    row = {"id": str(uuid4()), "userId": user_id, "resumeId": resume_id, "name": name}
    _PROFILES[row["id"]] = row
    return row


def notify(*, user_id: str, text: str, channel: str = "toast") -> dict[str, Any]:
    row = {"id": str(uuid4()), "userId": user_id, "text": text, "channel": channel}
    _TOASTS.append(row)
    return row


def digest_email(user_id: str) -> dict[str, Any]:
    items = [row for row in _TOASTS if row["userId"] == user_id]
    return {"userId": user_id, "count": len(items), "channel": "email"}


def audit_csv(events: list[dict[str, Any]]) -> dict[str, Any]:
    return audit_bundle(events=events)


def charts(points: list[dict[str, float]]) -> dict[str, Any]:
    return {"series": points, "page": "metrics"}


def a11y_label(kind: str) -> dict[str, str]:
    labels = {"list": "Job results", "detail": "Job details", "filter": "Job filters"}
    return {"aria-label": labels.get(kind, kind)}


def base_locale() -> dict[str, str]:
    return {"locale": "en", "jobs": "Jobs", "filters": "Filters"}


def mobile_layout(width: int) -> str:
    return "phone" if width <= 640 else "desktop"


def chips(reasons: list[str]) -> list[dict[str, str]]:
    return explanation_chips(reasons)


def seed() -> dict[str, Any]:
    return seed_v3()


def stale_preset(*, age_min: int) -> dict[str, Any]:
    return refresh_saved_search(stale_after_min=15, age_min=age_min)

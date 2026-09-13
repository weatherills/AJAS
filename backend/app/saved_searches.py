"""Saved-search CRUD used by Job Feed presets and the API."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.matching.keys import utc_now

_STORE: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _STORE.clear()


def create(*, user_id: str, name: str, filters: dict[str, Any], alerts: bool = False) -> dict[str, Any]:
    row = {
        "id": str(uuid4()),
        "userId": user_id,
        "name": name.strip(),
        "filters": dict(filters or {}),
        "alertsEnabled": bool(alerts),
        "updatedAt": utc_now(),
    }
    _STORE[row["id"]] = row
    return row


def listing(user_id: str) -> list[dict[str, Any]]:
    return [row for row in _STORE.values() if row["userId"] == user_id]


def update(search_id: str, user_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
    row = _STORE.get(search_id)
    if not row or row["userId"] != user_id:
        return None
    if "name" in patch:
        row["name"] = str(patch["name"]).strip()
    if "filters" in patch and isinstance(patch["filters"], dict):
        row["filters"] = dict(patch["filters"])
    if "alertsEnabled" in patch:
        row["alertsEnabled"] = bool(patch["alertsEnabled"])
    row["updatedAt"] = utc_now()
    return row


def delete(search_id: str, user_id: str) -> bool:
    row = _STORE.get(search_id)
    if not row or row["userId"] != user_id:
        return False
    del _STORE[search_id]
    return True

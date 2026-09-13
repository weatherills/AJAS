"""Thumbs up/down match feedback store."""

from __future__ import annotations

from typing import Any

_FEEDBACK: list[dict[str, Any]] = []


def record(*, user_id: str, match_id: str, thumb: str, note: str = "") -> dict[str, Any]:
    vote = "up" if str(thumb).lower() in {"up", "1", "true", "yes"} else "down"
    row = {"userId": user_id, "matchId": match_id, "thumb": vote, "note": note}
    _FEEDBACK.append(row)
    return row


def for_match(match_id: str) -> list[dict[str, Any]]:
    return [row for row in _FEEDBACK if row["matchId"] == match_id]


def summary() -> dict[str, int]:
    ups = sum(1 for row in _FEEDBACK if row["thumb"] == "up")
    downs = sum(1 for row in _FEEDBACK if row["thumb"] == "down")
    return {"up": ups, "down": downs, "total": len(_FEEDBACK)}


def reset() -> None:
    _FEEDBACK.clear()

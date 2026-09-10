"""Suppression list for bounce and complaint webhooks."""

from __future__ import annotations

from typing import Any

from app.mail.keys import utc_now

_rows: dict[str, dict[str, Any]] = {}


def normalize(address: str) -> str:
    return (address or "").strip().lower()


def suppress(address: str, *, reason: str, source: str = "webhook") -> dict[str, Any]:
    email = normalize(address)
    if not email or "@" not in email:
        raise ValueError("address is required")
    row = {
        "address": email,
        "reason": reason,
        "source": source,
        "suppressedAt": utc_now(),
    }
    _rows[email] = row
    return row


def is_suppressed(address: str) -> bool:
    return normalize(address) in _rows


def get(address: str) -> dict[str, Any] | None:
    return _rows.get(normalize(address))


def list_all() -> list[dict[str, Any]]:
    return list(_rows.values())

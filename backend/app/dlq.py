"""Dead-letter inspection with secret redaction and retry."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_SECRET_KEYS = {"authorization", "password", "token", "secret", "api_key", "apikey"}

_DLQ: list[dict[str, Any]] = []


def reset() -> None:
    _DLQ.clear()


def redact(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = deepcopy(payload)
    for key, value in list(redacted.items()):
        if key.lower() in _SECRET_KEYS:
            redacted[key] = "[redacted]"
        elif isinstance(value, dict):
            redacted[key] = redact(value)
    return redacted


def enqueue(item: dict[str, Any]) -> dict[str, Any]:
    stored = {"id": item.get("id") or f"dlq-{len(_DLQ)+1}", "payload": redact(item), "status": "dead"}
    _DLQ.append(stored)
    return stored


def inspect(item_id: str) -> dict[str, Any] | None:
    return next((item for item in _DLQ if item["id"] == item_id), None)


def retry(item_id: str) -> dict[str, Any] | None:
    item = inspect(item_id)
    if not item:
        return None
    item["status"] = "queued"
    return item


def listing() -> list[dict[str, Any]]:
    return list(_DLQ)

"""Retry optional-board fixture loads when listing DOM/API shape drifts."""

from __future__ import annotations

from typing import Any, Callable

from app.job_sources.drift import detect_change

DEFAULT_RETRIES = 3


def _strip_volatile(payload: Any) -> Any:
    """Heuristic: drop timestamps and etags that trip false-positive drift."""
    if isinstance(payload, dict):
        skip = {"ts", "timestamp", "etag", "retrieved_at", "generated_at"}
        return {key: _strip_volatile(value) for key, value in payload.items() if key.lower() not in skip}
    if isinstance(payload, list):
        return [_strip_volatile(item) for item in payload]
    return payload


def retry_on_drift(
    source: str,
    payload: Any,
    loader: Callable[[Any], list],
    *,
    retries: int = DEFAULT_RETRIES,
) -> dict[str, Any]:
    last: list = []
    attempts = 0
    changed = False
    for attempts in range(1, max(1, retries) + 1):
        snapshot = detect_change(source, _strip_volatile(payload))
        last = loader(payload)
        changed = bool(snapshot.get("changed"))
        if not changed or last:
            break
    return {
        "source": source,
        "attempts": attempts,
        "changed": changed,
        "jobs": last,
        "recovered": bool(last) or not changed,
    }

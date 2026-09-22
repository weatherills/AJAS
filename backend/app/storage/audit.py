"""In-process audit trail for Cosmos reads/writes (correlationId, latency, errorCode)."""

from __future__ import annotations

from typing import Any

_EVENTS: list[dict[str, Any]] = []
MAX_EVENTS = 200


def reset() -> None:
    _EVENTS.clear()


def events() -> list[dict[str, Any]]:
    return list(_EVENTS)


def emit(
    *,
    container: str,
    op: str,
    correlation_id: str = "",
    latency_ms: float = 0,
    error_code: str | None = None,
    status: str = "ok",
) -> dict[str, Any]:
    event = {
        "container": container,
        "op": op,
        "correlationId": correlation_id or container,
        "latencyMs": round(float(latency_ms), 3),
        "errorCode": error_code,
        "status": status,
    }
    _EVENTS.append(event)
    overflow = len(_EVENTS) - MAX_EVENTS
    if overflow > 0:
        del _EVENTS[:overflow]
    return event

"""In-process traces for ingestion → matching → review."""

from __future__ import annotations

from collections import deque
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.request_context import current_request_id, current_user_id

_MAX = 200
_traces: deque[dict[str, Any]] = deque(maxlen=_MAX)


def start_span(name: str, **attrs: Any) -> dict[str, Any]:
    span = {
        "traceId": current_request_id() or str(uuid4()),
        "spanId": str(uuid4()),
        "name": name,
        "userId": current_user_id(),
        "startedNs": perf_counter(),
        "attrs": attrs,
    }
    return span


def finish_span(span: dict[str, Any], *, ok: bool = True, error: str | None = None) -> dict[str, Any]:
    elapsed_ms = round((perf_counter() - float(span["startedNs"])) * 1000, 2)
    record = {
        "traceId": span["traceId"],
        "spanId": span["spanId"],
        "name": span["name"],
        "userId": span.get("userId"),
        "elapsedMs": elapsed_ms,
        "ok": ok,
        "error": error,
        "attrs": span.get("attrs") or {},
    }
    _traces.append(record)
    return record


def snapshot(*, limit: int = 50) -> dict[str, Any]:
    rows = list(_traces)[-limit:]
    rows.reverse()
    return {"items": rows, "count": len(_traces)}

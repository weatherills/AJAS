"""Tracing UI, quotas v2, retry jitter, audit export, drain, backfill, orphan sweep."""

from __future__ import annotations

import csv
import io
import random
from typing import Any

from app.audit import recent_actions
from app.audit_query import export_csv
from app.matching.keys import utc_now
from app.pipeline_trace import pipeline_trace_id, trace_stage
from app.source_quotas import dashboard, record as quota_record

_SPANS: list[dict[str, Any]] = []
_BURST: dict[str, dict[str, int]] = {}
_WORKERS: dict[str, str] = {}


def reset() -> None:
    _SPANS.clear()
    _BURST.clear()
    _WORKERS.clear()


def propagate(stage: str, *, trace_id: str | None = None, **attrs: Any) -> dict[str, Any]:
    span = trace_stage(stage, trace_id=trace_id or pipeline_trace_id(), **attrs)
    _SPANS.append(span)
    return span


def trace_viewer(*, trace_id: str | None = None) -> dict[str, Any]:
    rows = [row for row in _SPANS if not trace_id or row.get("traceId") == trace_id]
    return {"items": rows, "count": len(rows)}


def quotas_v2(source: str, *, daily: int, burst: int, used: int) -> dict[str, Any]:
    quota_record(source, fetched=used)
    hit_daily = used >= daily
    hit_burst = used >= burst
    _BURST[source] = {"daily": daily, "burst": burst, "used": used}
    return {"source": source, "dailyHit": hit_daily, "burstHit": hit_burst, "allowed": not hit_daily, "dashboard": list(dashboard())}


def jitter_backoff(attempt: int, *, base: float = 0.25, cap: float = 8.0, rng: random.Random | None = None) -> float:
    exp = min(cap, base * (2 ** max(0, attempt)))
    scatter = (rng or random.Random(attempt)).random() * exp * 0.25
    return round(min(cap, exp + scatter), 4)


def audit_bundle(events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    rows = events if events is not None else list(recent_actions(50))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=sorted({k for row in rows for k in row.keys()}) or ["id"])
    if rows:
        writer.writeheader()
        writer.writerows(rows)
    return {"csv": buf.getvalue() or export_csv(), "json": rows, "count": len(rows)}


def drain_worker(name: str) -> dict[str, Any]:
    _WORKERS[name] = "draining"
    return {"worker": name, "status": "draining", "accepting": False}


def shutdown_worker(name: str) -> dict[str, Any]:
    drain_worker(name)
    _WORKERS[name] = "stopped"
    return {"worker": name, "status": "stopped", "graceful": True}


def backfill_chunks(ids: list[str], *, size: int = 25) -> dict[str, Any]:
    chunks = [ids[i : i + size] for i in range(0, len(ids), size)]
    return {"chunks": chunks, "count": len(chunks), "size": size, "progress": 0, "status": "ready"}


def sweep_orphans(records: list[dict[str, Any]], *, live_ids: set[str]) -> dict[str, Any]:
    orphaned = [row for row in records if str(row.get("id")) not in live_ids]
    return {"orphans": orphaned, "count": len(orphaned), "at": utc_now()}

"""Refresh cadence, ingest metrics, and failure alerting for extra boards."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.flags import feature_enabled
from app.integrations.ingest import indeed_ingest, linkedin_ingest, reset_limiter
from app.job_sources.boards import SOURCE_FLAGS
from app.job_sources.keys import utc_now
from app.notify import push as notify_push

ALERT_AFTER = 3
FetchFn = Callable[..., dict[str, Any]]

_STATE: dict[str, dict[str, Any]] = {}
_FETCHERS: dict[str, FetchFn] = {"indeed": indeed_ingest, "linkedin": linkedin_ingest}


def reset() -> None:
    _STATE.clear()
    reset_limiter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def snapshot(source: str | None = None) -> dict[str, Any]:
    if source:
        return dict(_STATE.get(source) or {"source": source, "runs": 0, "consecutiveFailures": 0})
    return {key: dict(value) for key, value in _STATE.items()}


def due(source: str, *, cadence_seconds: int = 3600, now: datetime | None = None) -> bool:
    row = _STATE.get(source) or {}
    last = _parse(row.get("lastRunAt"))
    if last is None:
        return True
    stamp = now or _now()
    return stamp >= last + timedelta(seconds=int(cadence_seconds))


def record_run(source: str, result: dict[str, Any], *, failed: bool = False) -> dict[str, Any]:
    prev = _STATE.get(source) or {
        "source": source,
        "runs": 0,
        "consecutiveFailures": 0,
        "ingested": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "alerts": 0,
    }
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    prev["runs"] = int(prev.get("runs") or 0) + 1
    prev["lastRunAt"] = utc_now()
    prev["lastReason"] = result.get("reason")
    for key in ("ingested", "updated", "skipped", "failed"):
        prev[key] = int(prev.get(key) or 0) + int(metrics.get(key) or 0)
    if failed or result.get("reason") not in {"ok", "flag_off"}:
        prev["consecutiveFailures"] = int(prev.get("consecutiveFailures") or 0) + 1
    else:
        prev["consecutiveFailures"] = 0
    if int(prev["consecutiveFailures"]) >= ALERT_AFTER:
        prev["alerts"] = int(prev.get("alerts") or 0) + 1
        notify_push(
            kind="ingest_failure",
            title=f"{source} ingest failing",
            body=f"{prev['consecutiveFailures']} consecutive failures ({result.get('reason')})",
        )
    _STATE[source] = prev
    return dict(prev)


def tick(
    *,
    payloads: dict[str, Any] | None = None,
    cadence_seconds: int = 3600,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run due extra-board ingests when their flags are on. No-op when flags are off."""
    ran: list[str] = []
    skipped: list[str] = []
    results: dict[str, Any] = {}
    body = payloads or {}
    for source, fetch in _FETCHERS.items():
        flag = SOURCE_FLAGS.get(source)
        if not flag or not feature_enabled(flag):
            skipped.append(source)
            continue
        if not due(source, cadence_seconds=cadence_seconds, now=now):
            skipped.append(source)
            continue
        payload = body.get(source) or {"jobs": []}
        result = fetch(payload, search={"cadenceSeconds": cadence_seconds})
        failed = result.get("reason") not in {"ok", "flag_off"}
        results[source] = result
        record_run(source, result, failed=failed)
        ran.append(source)
    return {"ran": ran, "skipped": skipped, "results": results, "state": snapshot()}

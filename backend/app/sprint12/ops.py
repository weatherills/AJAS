"""Health dashboard, logs UI query, alert routing, backup/DR, CI, flaky tests, synthetics."""

from __future__ import annotations

import random
from typing import Any

from app.sprint12 import VERSION

_LOGS: list[dict[str, Any]] = []
_ONCALL: dict[str, dict[str, Any]] = {}
_FLAKY: dict[str, dict[str, Any]] = {}
_BACKUPS: list[dict[str, Any]] = []


def reset() -> None:
    _LOGS.clear()
    _ONCALL.clear()
    _FLAKY.clear()
    _BACKUPS.clear()


def health_overview(*, storage: str, workers: dict[str, bool]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": "ok" if all(workers.values()) else "degraded",
        "storage": storage,
        "workers": workers,
        "goldenSignals": {
            "latencyMs": 42,
            "trafficRpm": 12,
            "errors": 0,
            "saturation": 0.18,
        },
    }


def ingest_log(level: str, message: str, **fields: Any) -> dict[str, Any]:
    row = {"level": level, "message": message, **fields}
    _LOGS.append(row)
    return row


def search_logs(*, level: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    rows = list(_LOGS)
    if level:
        rows = [row for row in rows if row.get("level") == level]
    if q:
        needle = q.lower()
        rows = [row for row in rows if needle in str(row.get("message", "")).lower()]
    return rows


def set_oncall(schedule: list[dict[str, str]]) -> dict[str, Any]:
    if not schedule:
        raise ValueError("empty schedule")
    _ONCALL["primary"] = schedule[0]
    _ONCALL["escalation"] = schedule[1:]
    return {"primary": schedule[0], "escalation": schedule[1:], "policy": "page-then-slack"}


def route_alert(severity: str) -> dict[str, Any]:
    primary = _ONCALL.get("primary") or {"name": "unassigned"}
    if severity == "critical":
        targets = [primary] + list(_ONCALL.get("escalation") or [])
    else:
        targets = [primary]
    return {"severity": severity, "notified": targets}


def nightly_backup(*, stores: list[str]) -> dict[str, Any]:
    row = {"stores": list(stores), "status": "ok", "rpoMinutes": 60, "rtoMinutes": 30}
    _BACKUPS.append(row)
    return row


def restore_playbook() -> list[str]:
    return [
        "Snapshot Cosmos to ajas-restore-drill",
        "Copy blob containers to *-restore",
        "Point staging Functions at restored account",
        "GET /api/health then GET /api/v1/settings",
        "Tear down drill account and log duration",
    ]


def dr_checklist() -> dict[str, Any]:
    return {
        "rpo": "1h",
        "rto": "30m",
        "lastDrill": _BACKUPS[-1] if _BACKUPS else None,
        "steps": restore_playbook(),
    }


def ci_plan() -> dict[str, Any]:
    return {
        "backend": {"parallel": "pytest -n auto", "cache": "pip"},
        "frontend": {"parallel": False, "cache": "npm"},
        "coverageTarget": 0.8,
        "coverageGate": 0.4,
    }


def record_flaky(test_id: str, *, failed: bool) -> dict[str, Any]:
    row = _FLAKY.setdefault(test_id, {"fails": 0, "runs": 0, "quarantined": False})
    row["runs"] += 1
    if failed:
        row["fails"] += 1
    if row["runs"] >= 3 and row["fails"] / row["runs"] >= 0.5:
        row["quarantined"] = True
    return dict(row)


def synthetic_job(*, seed: str = "acme") -> dict[str, Any]:
    rng = random.Random(seed)
    titles = ["Staff Engineer", "Product Designer", "Data Scientist"]
    return {
        "id": f"syn-{seed}",
        "title": titles[rng.randrange(len(titles))],
        "company": seed.title(),
        "location": "Remote",
        "description": "Build reliable systems. Python, TypeScript, Azure.",
    }


def synthetic_resume(*, seed: str = "ada") -> dict[str, Any]:
    return {
        "id": f"resume-{seed}",
        "name": seed.title(),
        "skills": ["python", "typescript", "azure"],
        "email": f"{seed}@example.test",
    }


def synthetic_email(*, kind: str = "interview") -> dict[str, Any]:
    subjects = {
        "interview": "Interview next Tuesday 2026-09-15 14:00",
        "reject": "Unfortunately we are not moving forward",
        "offer": "Offer and compensation package",
    }
    return {"subject": subjects.get(kind, "Hello"), "kind": kind}


def queue_inspector() -> dict[str, Any]:
    from app.dlq import listing

    items = listing()
    return {"items": items, "count": len(items)}


def idempotency_monitor() -> dict[str, Any]:
    from app.idempotency_v2 import conflicts

    rows = conflicts()
    return {"duplicates": rows, "count": len(rows)}


def adapter_charts() -> list[dict[str, object]]:
    from app.source_metrics import histogram
    from app.source_quotas import dashboard

    quota_rows = list(dashboard())
    charts: list[dict[str, object]] = [{**row, "kind": "quota"} for row in quota_rows]
    for row in quota_rows:
        source = str(row.get("source") or "")
        if source:
            charts.append({**histogram(source), "kind": "latency"})
    return charts

def rate_policy_ui() -> dict[str, object]:
    from app.source_quotas import dashboard
    return {"quotas": list(dashboard()), "toggles": True}


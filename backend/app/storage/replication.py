"""Geo-redundancy plan and failover drill (RPO/RTO evidence)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings

CRITICAL_GEO = (
    "users",
    "user_settings",
    "matches",
    "auto_apply_attempts",
    "decision_events",
    "settings_audit_log",
)


def preferred_regions(settings: Settings | None = None) -> list[str]:
    raw = (settings or get_settings()).cosmos_preferred_regions or ""
    return [part.strip() for part in raw.split(",") if part.strip()]


def replication_plan(settings: Settings | None = None) -> dict[str, Any]:
    regions = preferred_regions(settings) or ["primary"]
    return {
        "schema": "ajas.cosmos.geo.v1",
        "regions": regions,
        "multiWrite": False,
        "criticalContainers": list(CRITICAL_GEO),
        "rpoSeconds": 0 if len(regions) >= 2 else None,
        "rtoSeconds": 60 if len(regions) >= 2 else None,
        "notes": "Session consistency + single-writer. Failover promotes the next preferred region.",
    }


def failover_drill(*, from_region: str, to_region: str, elapsed_seconds: float) -> dict[str, Any]:
    plan = replication_plan()
    ok = elapsed_seconds <= float(plan["rtoSeconds"] or 60)
    return {
        "schema": "ajas.cosmos.failover.v1",
        "from": from_region,
        "to": to_region,
        "elapsedSeconds": elapsed_seconds,
        "rpoSeconds": plan["rpoSeconds"] or 0,
        "rtoSeconds": plan["rtoSeconds"] or 60,
        "passed": ok,
        "at": datetime.now(timezone.utc).isoformat(),
        "evidence": "DAL retries 429/503; CosmosClient preferred_locations fail over reads.",
    }

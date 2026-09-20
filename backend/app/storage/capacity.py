"""Autoscale / serverless RU capacity, daily budgets, and IaC plan."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.storage.catalog import container_catalog
from app.storage.ops import _alert

HOT_CONTAINERS = frozenset(
    {"matches", "resumes", "auto_apply_attempts", "job_postings_canonical", "email_threads", "user_settings"}
)


def throughput_mode(settings: Settings | None = None) -> str:
    mode = (settings or get_settings()).cosmos_throughput_mode or "serverless"
    return mode.strip().lower()


def autoscale_max_ru(container_id: str, settings: Settings | None = None) -> int | None:
    cfg = settings or get_settings()
    if throughput_mode(cfg) != "autoscale":
        return None
    base = int(cfg.cosmos_autoscale_max_ru or 4000)
    return base if container_id in HOT_CONTAINERS else max(1000, base // 4)


def capacity_plan(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    mode = throughput_mode(cfg)
    rows = []
    for spec in container_catalog():
        rows.append(
            {
                "id": spec.id,
                "mode": mode,
                "maxRu": autoscale_max_ru(spec.id, cfg),
                "hot": spec.id in HOT_CONTAINERS,
            }
        )
    return {
        "schema": "ajas.cosmos.capacity.v1",
        "mode": mode,
        "dailyRuBudget": int(cfg.cosmos_daily_ru_budget or 0),
        "containers": rows,
        "iac": "infra/cosmos-autoscale.bicep",
    }


def daily_ru_dashboard(*, ru_today: float, settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    budget = float(cfg.cosmos_daily_ru_budget or 0)
    snap = {
        "schema": "ajas.cosmos.ru.daily.v1",
        "ruToday": float(ru_today),
        "budget": budget,
        "utilization": (float(ru_today) / budget) if budget else 0.0,
    }
    alerts = []
    if budget and float(ru_today) >= budget:
        alerts.append(_alert("cosmos.daily_ru", ru_today, "Daily RU budget exhausted"))
    return {"snapshot": snap, "alerts": alerts, "firing": bool(alerts)}


def bicep_autoscale_snippet() -> str:
    return (
        "resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {\n"
        "  properties: {\n"
        "    enableMultipleWriteLocations: false\n"
        "    locations: [\n"
        "      { locationName: primary, failoverPriority: 0 }\n"
        "      { locationName: secondary, failoverPriority: 1 }\n"
        "    ]\n"
        "  }\n"
        "}\n"
    )

"""Scheduled retention executor wrapping the purge planner."""

from __future__ import annotations

from typing import Any

from app.retention import apply_purge, plan_purge


def run_scheduled(*, jobs: list[dict[str, Any]], emails: list[dict[str, Any]], store: Any | None = None) -> dict[str, Any]:
    plan = plan_purge(jobs=jobs, emails=emails)
    result = apply_purge(store, plan)
    return {"plan": plan, "result": result, "scheduled": True}

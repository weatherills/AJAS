"""Per-container Cosmos consistency and read-your-writes checks."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings

STRONG = frozenset(
    {"user_settings", "email_connections", "submit_requests", "schema_migrations", "form_autofill_values"}
)
ALLOWED = frozenset({"Session", "Strong", "BoundedStaleness", "ConsistentPrefix", "Eventual"})


def _normalize(level: str) -> str:
    if level.lower() == "strong":
        return "Strong"
    if level.lower() == "session":
        return "Session"
    if level in ALLOWED:
        return level
    titled = level[:1].upper() + level[1:]
    return titled if titled in ALLOWED else "Session"


def container_consistency(container: str, settings: Settings | None = None) -> str:
    per_container = "Strong" if container in STRONG else "Session"
    override = ((settings or get_settings()).cosmos_consistency or "").strip()
    if not override:
        return per_container
    normalized = _normalize(override)
    # Account default Session keeps write-critical containers on Strong.
    if normalized == "Session":
        return per_container
    return normalized


def consistency_plan(settings: Settings | None = None) -> dict[str, Any]:
    from app.storage.catalog import container_catalog

    cfg = settings or get_settings()
    return {
        "schema": "ajas.cosmos.consistency.v1",
        "override": (cfg.cosmos_consistency or "").strip() or None,
        "containers": {spec.id: container_consistency(spec.id, cfg) for spec in container_catalog()},
        "rationale": {
            "Strong": "Settings, tokens, submit idempotency — read-your-writes across instances.",
            "Session": "Queue lists and telemetry — same session token is enough for the UI.",
        },
    }

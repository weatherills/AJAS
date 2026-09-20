"""Expand-only schema versioning and stored-logic deployment."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.storage.catalog import ensure_all_containers
from app.storage.dal import CosmosDAL
from app.storage.sprocs import SCHEMA_VERSION, SCRIPT_VERSION, deploy_stored_logic, stored_logic_catalog

MIGRATIONS: tuple[dict[str, Any], ...] = (
    {
        "id": SCHEMA_VERSION,
        "version": 1,
        "description": "Bootstrap containers, indexing, TTL, and stored logic v1.",
    },
)


def current_schema_version() -> str:
    return SCHEMA_VERSION


def migration_plan() -> list[dict[str, Any]]:
    return [dict(item) for item in MIGRATIONS]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_migration(dal: CosmosDAL, *, result: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": SCHEMA_VERSION,
        "schemaVersion": 1,
        "version": 1,
        "scriptVersion": SCRIPT_VERSION,
        "scripts": [item["id"] for item in stored_logic_catalog()],
        "applied_at": _now(),
        "result": {"containers": len(result.get("containers") or {}), "scripts": result.get("scripts")},
    }
    dal.upsert("schema_migrations", row)
    return row


def apply_migrations(database: Any) -> dict[str, Any]:
    """Create missing containers, (re)deploy sprocs, record schema_migrations."""
    created = ensure_all_containers(database)
    logic = deploy_stored_logic(database, containers=created)
    dal = CosmosDAL(database)
    record = record_migration(dal, result=logic)
    return {
        "status": "applied",
        "schemaVersion": SCHEMA_VERSION,
        "containers": created,
        "storedLogic": logic,
        "record": record,
    }

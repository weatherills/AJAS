"""Versioned Cosmos stored procedures, UDFs, and triggers.

Cosmos pre/post triggers cannot call Azure Storage Queues. The post-trigger
stamps an ``_enqueue`` hint; application code uses ``enqueue_hint_for`` to
dispatch the matching queue message after a successful write.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent / "scripts"
SCHEMA_VERSION = "ajas.cosmos.v1"
SCRIPT_VERSION = 1

ENQUEUE_ON_WRITE: dict[str, str] = {
    "submit_requests": "auto-apply-submits",
    "auto_apply_attempts": "auto-apply-requests",
    "match_runs": "match-compute",
    "source_fetch_runs": "crawl-runs",
    "resume_parse_events": "resume-parse",
}


def _script(name: str) -> str:
    return (SCRIPTS_DIR / name).read_text(encoding="utf-8")


def stored_logic_catalog() -> list[dict[str, Any]]:
    return [
        {
            "kind": "sproc",
            "id": "sp_safeUpsert",
            "file": "sp_safeUpsert.js",
            "version": SCRIPT_VERSION,
            "body": _script("sp_safeUpsert.js"),
            "purpose": "Versioned upsert that rejects stale schemaVersion values.",
        },
        {
            "kind": "udf",
            "id": "udf_avgScore",
            "file": "udf_avgScore.js",
            "version": SCRIPT_VERSION,
            "body": _script("udf_avgScore.js"),
            "purpose": "Average match scores for in-container aggregation.",
        },
        {
            "kind": "trigger",
            "id": "trg_setTimestamps",
            "file": "trg_setTimestamps.js",
            "version": SCRIPT_VERSION,
            "body": _script("trg_setTimestamps.js"),
            "triggerType": "Pre",
            "triggerOperation": "All",
            "purpose": "Stamp created_at / updated_at / schemaVersion on write.",
        },
        {
            "kind": "trigger",
            "id": "trg_enqueueHint",
            "file": "trg_enqueueHint.js",
            "version": SCRIPT_VERSION,
            "body": _script("trg_enqueueHint.js"),
            "triggerType": "Post",
            "triggerOperation": "Create",
            "purpose": "Stamp _enqueue hint after writes that start a pipeline.",
        },
    ]


def apply_timestamps(doc: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    stamp = now or datetime.now(timezone.utc).isoformat()
    out = dict(doc)
    out.setdefault("created_at", stamp)
    out["updated_at"] = stamp
    out.setdefault("schemaVersion", 1)
    return out


def avg_score(scores: list[Any] | None) -> float:
    values = [float(item) for item in (scores or []) if item is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)


def enqueue_hint_for(container: str, doc: dict[str, Any]) -> dict[str, Any] | None:
    queue = ENQUEUE_ON_WRITE.get(container)
    if not queue:
        return None
    return {"queue": queue, "documentId": doc.get("id"), "container": container}


class StaleVersionError(ValueError):
    """Incoming schemaVersion is older than the stored document."""


def safe_upsert_document(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    """Python equivalent of ``sp_safeUpsert`` for unit tests and in-memory stores."""
    now = datetime.now(timezone.utc).isoformat()
    doc = dict(incoming)
    if existing:
        incoming_version = int(doc.get("schemaVersion") or 0)
        current = int(existing.get("schemaVersion") or 0)
        if incoming_version and current and incoming_version < current:
            raise StaleVersionError("stale schemaVersion")
        doc["schemaVersion"] = current + 1
        doc["created_at"] = existing.get("created_at") or now
        doc["updated_at"] = now
        return doc
    doc["schemaVersion"] = int(doc.get("schemaVersion") or 0) + 1
    doc.setdefault("created_at", now)
    doc["updated_at"] = now
    return doc


def _scripts_api(container: Any) -> Any:
    return getattr(container, "scripts", None)


def _upsert_script(api: Any, kind: str, body: dict[str, Any]) -> str:
    create = {
        "sproc": ("create_stored_procedure", "upsert_stored_procedure", "delete_stored_procedure"),
        "udf": ("create_user_defined_function", "upsert_user_defined_function", "delete_user_defined_function"),
        "trigger": ("create_trigger", "upsert_trigger", "delete_trigger"),
    }[kind]
    upsert_name, create_name, delete_name = create[1], create[0], create[2]
    upsert = getattr(api, upsert_name, None)
    if callable(upsert):
        upsert(body=body)
        return "upserted"
    try:
        getattr(api, create_name)(body=body)
        return "created"
    except Exception:
        deleter = getattr(api, delete_name, None)
        if callable(deleter):
            try:
                deleter(body["id"])
            except Exception:
                pass
        getattr(api, create_name)(body=body)
        return "replaced"


def deploy_stored_logic(database: Any, *, containers: list[str] | None = None) -> dict[str, Any]:
    """Idempotently deploy versioned sprocs/UDFs/triggers onto each container."""
    from app.storage.catalog import container_catalog

    ids = containers or [spec.id for spec in container_catalog()]
    deployed: dict[str, list[str]] = {}
    catalog = stored_logic_catalog()
    for container_id in ids:
        client = database.get_container_client(container_id)
        api = _scripts_api(client)
        names: list[str] = []
        if api is None:
            register = getattr(client, "register_script", None)
            if callable(register):
                for item in catalog:
                    register(item)
                    names.append(item["id"])
            deployed[container_id] = names
            continue
        for item in catalog:
            body: dict[str, Any] = {"id": item["id"], "body": item["body"]}
            if item["kind"] == "trigger":
                body["triggerType"] = item["triggerType"]
                body["triggerOperation"] = item["triggerOperation"]
            _upsert_script(api, item["kind"], body)
            names.append(item["id"])
        deployed[container_id] = names
    return {
        "schemaVersion": SCHEMA_VERSION,
        "scriptVersion": SCRIPT_VERSION,
        "containers": deployed,
        "scripts": [item["id"] for item in catalog],
    }

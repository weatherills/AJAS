"""Retention windows and GDPR-style user delete with an audit receipt."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

from app.flags import feature_enabled
from app.storage.blob_layout import blob_container_names, user_prefix
from app.storage.catalog import user_scoped_containers

# Durable records are purged by this job (not Cosmos TTL). TTL is reserved
# for scrape payloads, fetch attempts, ingest events, and webhooks.
RETENTION_DAYS: dict[str, int] = {
    "jobs": 365,
    "emails": 180,
    "logs": 30,
    "matches": 365,
    "resumes": 730,
    "applications": 547,  # 18 months — Auto-Apply / Matching PRDs
    "webhooks": 90,
    "match_runs": 547,
    "candidates": 730,
    "outbox": 30,
}

AUDIT_RETAIN_CONTAINERS = frozenset({"settings_audit_log"})
GDPR_EVENT = "GDPR_DELETE"


class DocumentStore(Protocol):
    def list_user_documents(self, container: str, user_id: str) -> list[dict[str, Any]]: ...

    def delete_document(self, container: str, item_id: str, partition_key: Any) -> None: ...

    def write_event(self, body: dict[str, Any]) -> None: ...

    def delete_blobs(self, container: str, prefix: str) -> int: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_stale(stamp: str | None, *, days: int, now: datetime | None = None) -> bool:
    if not stamp or days <= 0:
        return False
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed < (now or _now()) - timedelta(days=days)


def retention_plan(
    *,
    jobs: list[dict[str, Any]] | None = None,
    emails: list[dict[str, Any]] | None = None,
    matches: list[dict[str, Any]] | None = None,
    resumes: list[dict[str, Any]] | None = None,
    applications: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    clock = now or _now()

    def _ids(rows: list[dict[str, Any]] | None, artifact: str, *stamp_keys: str) -> list[str]:
        found: list[str] = []
        for row in rows or []:
            stamp = next((row.get(key) for key in stamp_keys if row.get(key)), None)
            if is_stale(stamp, days=RETENTION_DAYS[artifact], now=clock) and row.get("id"):
                found.append(str(row["id"]))
        return found

    return {
        "schema": "ajas.retention.v2",
        "enabled": feature_enabled("data_retention_purge"),
        "days": dict(RETENTION_DAYS),
        "jobIds": _ids(jobs, "jobs", "seen_last_at", "updated_at", "created_at"),
        "emailIds": _ids(emails, "emails", "received_at", "created_at"),
        "matchIds": _ids(matches, "matches", "queued_at", "created_at"),
        "resumeIds": _ids(resumes, "resumes", "updated_at", "created_at"),
        "applicationIds": _ids(applications, "applications", "updated_at", "created_at"),
    }


def apply_retention(store: DocumentStore | None, plan: dict[str, Any]) -> dict[str, Any]:
    if not plan.get("enabled"):
        return {"skipped": True, "deleted": 0}
    if store is None:
        deleted = sum(len(plan.get(key) or []) for key in ("jobIds", "emailIds", "matchIds", "resumeIds", "applicationIds"))
        return {"skipped": False, "deleted": deleted, "dryRun": True}
    deleted = 0
    mapping = (
        ("job_postings_canonical", "jobIds"),
        ("email_messages", "emailIds"),
        ("matches", "matchIds"),
        ("resumes", "resumeIds"),
        ("auto_apply_attempts", "applicationIds"),
    )
    for container, key in mapping:
        for item_id in plan.get(key) or []:
            store.delete_document(container, item_id, item_id)
            deleted += 1
    return {"skipped": False, "deleted": deleted, "dryRun": False}


def gdpr_plan(user_id: str) -> dict[str, Any]:
    containers = [spec.id for spec in user_scoped_containers() if spec.id not in AUDIT_RETAIN_CONTAINERS]
    return {
        "schema": "ajas.gdpr.delete.v1",
        "userId": user_id,
        "containers": containers,
        "blobPrefixes": {name: user_prefix(user_id) for name in blob_container_names()},
        "retain": sorted(AUDIT_RETAIN_CONTAINERS),
        "eventType": GDPR_EVENT,
    }


def execute_gdpr_delete(store: DocumentStore, user_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    plan = gdpr_plan(user_id)
    deleted_docs = 0
    deleted_blobs = 0
    per_container: dict[str, int] = {}
    for container in plan["containers"]:
        rows = store.list_user_documents(container, user_id)
        count = 0
        for row in rows:
            item_id = str(row.get("id") or "")
            if not item_id:
                continue
            pk_field = next(
                (item.partition_key.lstrip("/") for item in user_scoped_containers() if item.id == container),
                "user_id",
            )
            pk = row.get(pk_field) or row.get("user_id") or row.get("userId") or user_id
            store.delete_document(container, item_id, pk)
            count += 1
        per_container[container] = count
        deleted_docs += count
    for blob_container, prefix in plan["blobPrefixes"].items():
        deleted_blobs += int(store.delete_blobs(blob_container, prefix) or 0)
    receipt = {
        "id": str(uuid4()),
        "user_id": user_id,
        "event_type": GDPR_EVENT,
        "entity_type": "user",
        "entity_id": user_id,
        "payload": {
            "deletedDocs": deleted_docs,
            "deletedBlobs": deleted_blobs,
            "containers": per_container,
            "retained": plan["retain"],
        },
        "occurred_at": (now or _now()).isoformat(),
    }
    store.write_event(receipt)
    return {
        "status": "purged",
        "userId": user_id,
        "deletedDocs": deleted_docs,
        "deletedBlobs": deleted_blobs,
        "audit": receipt,
        "retained": plan["retain"],
    }

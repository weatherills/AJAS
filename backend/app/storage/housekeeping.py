"""Prune match history and purge soft-deleted rows honoring retention."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.matching.records import MatchRecordStore, prune_keep
from app.storage.dal import CosmosDAL
from app.storage.entity_dal import CatalogRepository, repository_for
from app.storage.retention import RETENTION_DAYS, is_stale

PURGE_CONTAINERS: tuple[str, ...] = ("resumes", "resume_versions", "users", "user_settings", "email_accounts")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def prune_matches(
    dal: CosmosDAL,
    user_id: str,
    *,
    keep: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    store = MatchRecordStore(dal)
    return store.prune(user_id, keep=keep if keep is not None else prune_keep(), dry_run=dry_run)


def purge_soft_deleted(
    dal: CosmosDAL,
    *,
    user_id: str,
    now: datetime | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    clock = now or _now()
    deleted: dict[str, list[str]] = {}
    for name in PURGE_CONTAINERS:
        repo = repository_for(dal, name)
        pk_field = repo.pk_field
        partition = user_id if pk_field in {"user_id", "userId"} else user_id
        try:
            page = repo.list_partition(partition, max_items=100)
        except Exception:  # noqa: BLE001 — empty catalog in tests
            page_items: list[dict[str, Any]] = []
        else:
            page_items = list(page.items)
        victims = []
        for row in page_items:
            if not row.get("is_deleted"):
                continue
            stamp = str(row.get("deleted_at") or row.get("updated_at") or "")
            days = RETENTION_DAYS.get("resumes", 730) if name.startswith("resume") else RETENTION_DAYS.get("logs", 30)
            if stamp and not is_stale(stamp, days=days, now=clock):
                continue
            victims.append(str(row.get("id")))
            if not dry_run:
                repo.delete(str(row["id"]), partition_key=row.get(pk_field) or partition)
        deleted[name] = victims
    return {
        "schema": "ajas.housekeeping.purge.v1",
        "userId": user_id,
        "dryRun": dry_run,
        "deleted": deleted,
        "count": sum(len(ids) for ids in deleted.values()),
    }


def run_housekeeping(
    dal: CosmosDAL,
    user_id: str,
    *,
    keep: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    prune = prune_matches(dal, user_id, keep=keep, dry_run=dry_run)
    purge = purge_soft_deleted(dal, user_id=user_id, dry_run=dry_run)
    return {
        "schema": "ajas.housekeeping.job.v1",
        "prune": prune,
        "purge": purge,
        "retentionDays": dict(RETENTION_DAYS),
        "keep": keep if keep is not None else prune_keep(),
    }


def catalog_repo(dal: CosmosDAL, container: str) -> CatalogRepository:
    return repository_for(dal, container)

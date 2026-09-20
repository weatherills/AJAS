"""Chunked schema backfill with RU budget guards."""

from __future__ import annotations

from typing import Any, Callable

from app.storage.dal import CosmosDAL

Mutator = Callable[[dict[str, Any]], dict[str, Any] | None]


class RuBudgetExceeded(RuntimeError):
    """Backfill stopped because the RU budget for this run was exhausted."""


def run_backfill(
    dal: CosmosDAL,
    container: str,
    mutate: Mutator,
    *,
    chunk_size: int = 50,
    ru_budget: float = 400.0,
    partition_key: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    scanned = 0
    updated = 0
    skipped = 0
    ru = 0.0
    token: str | None = None
    while True:
        page = dal.query(
            container,
            "SELECT * FROM c",
            partition_key=partition_key,
            continuation=token,
            max_items=chunk_size,
            allow_cross_partition=partition_key is None,
        )
        ru += float(page.request_charge or 0)
        if ru > ru_budget:
            raise RuBudgetExceeded(f"{container} spent {ru} RU (budget {ru_budget})")
        for row in page.items:
            scanned += 1
            next_row = mutate(dict(row))
            if next_row is None or next_row == row:
                skipped += 1
                continue
            if not dry_run:
                dal.upsert(container, next_row)
            updated += 1
        token = page.continuation
        if not token:
            break
    return {
        "schema": "ajas.cosmos.backfill.v2",
        "container": container,
        "scanned": scanned,
        "updated": updated,
        "skipped": skipped,
        "ru": ru,
        "dryRun": dry_run,
        "chunkSize": chunk_size,
    }

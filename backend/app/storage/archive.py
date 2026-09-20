"""Cold archive of aged Cosmos documents into Blob, with restore."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from app.storage.backup import load_jsonl
from app.storage.blob_layout import BlobContainer
from app.storage.retention import is_stale

ARCHIVE_CONTAINER = "cosmos-archive"

ARCHIVE_SPEC = BlobContainer(
    name=ARCHIVE_CONTAINER,
    purpose="Cold Cosmos JSONL for logs/audit older than the hot retention window",
    key_pattern="{container}/{yyyy}/{mm}/{id}.json",
    metadata_tags=("container", "id", "archived_at"),
    cool_after_days=30,
    delete_after_days=2555,
)


def archive_key(container: str, item_id: str, archived_at: str) -> str:
    stamp = archived_at.replace(":", "")[:10]
    year = stamp[:4]
    month = stamp[5:7] if len(stamp) >= 7 else "01"
    return f"{container}/{year}/{month}/{item_id}.json"


def archive_stale(
    dal: Any,
    *,
    container: str,
    stamp_keys: tuple[str, ...] = ("created_at", "updated_at", "occurred_at"),
    days: int = 365,
    put: Callable[[str, str, bytes], None] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    page = dal.query(container, "SELECT * FROM c", max_items=100, allow_cross_partition=True)
    moved = 0
    restored_ready = 0
    for row in page.items:
        stamp = next((row.get(key) for key in stamp_keys if row.get(key)), None)
        if not is_stale(stamp, days=days, now=clock):
            continue
        item_id = str(row.get("id") or "")
        archived_at = clock.isoformat()
        key = archive_key(container, item_id, archived_at)
        if put:
            put(ARCHIVE_CONTAINER, key, dump_bytes(row))
        pk = row.get("user_id") or row.get("id")
        dal.delete(container, item_id, partition_key=pk)
        moved += 1
        restored_ready += 1
    return {
        "schema": "ajas.cosmos.archive.v1",
        "container": container,
        "moved": moved,
        "blobContainer": ARCHIVE_CONTAINER,
        "restoreReady": restored_ready,
    }


def dump_bytes(row: dict[str, Any]) -> bytes:
    import json

    return (json.dumps(row, default=str) + "\n").encode("utf-8")


def restore_from_jsonl(dal: Any, path, *, container: str) -> int:
    rows = load_jsonl(path)
    for row in rows:
        dal.upsert(container, row)
    return len(rows)

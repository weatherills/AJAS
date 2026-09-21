"""Resume version documents: blob metadata, soft-delete, TTL on removal."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.storage.epic import VERSION_TTL_SECONDS


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def version_document(
    *,
    version_id: str,
    resume_id: str,
    user_id: str,
    version: int,
    blob_uri: str,
    original_filename: str,
    mime_type: str = "application/pdf",
    file_size: int = 0,
    checksum_sha256: str = "",
    is_deleted: bool = False,
    created_at: str | None = None,
) -> dict[str, Any]:
    now = created_at or stamp()
    row: dict[str, Any] = {
        "id": version_id,
        "resume_id": resume_id,
        "user_id": user_id,
        "version": version,
        "blob_uri": blob_uri,
        "original_filename": original_filename,
        "mime_type": mime_type,
        "file_size": file_size,
        "checksum_sha256": checksum_sha256,
        "is_deleted": is_deleted,
        "deleted_at": now if is_deleted else None,
        "created_at": now,
        "updated_at": now,
    }
    if is_deleted:
        row["ttl"] = VERSION_TTL_SECONDS
    return row


def mark_removed(row: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    out = dict(row)
    out["is_deleted"] = True
    out["deleted_at"] = now or stamp()
    out["ttl"] = VERSION_TTL_SECONDS
    out["updated_at"] = out["deleted_at"]
    return out

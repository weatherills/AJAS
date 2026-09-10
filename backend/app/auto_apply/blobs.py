"""Blob SAS helpers for Auto-Apply artifacts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.auto_apply.constants import SAS_TTL_MINUTES


class AutoApplyBlobStore(Protocol):
    def sas_url(self, blob_path: str, *, minutes: int = SAS_TTL_MINUTES) -> str: ...

    def put(self, blob_path: str, data: bytes) -> None: ...

    def get(self, blob_path: str) -> bytes | None: ...


class InMemoryBlobStore:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def sas_url(self, blob_path: str, *, minutes: int = SAS_TTL_MINUTES) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return f"https://blob.local/{blob_path}?se={expiry.strftime('%Y-%m-%dT%H:%M:%SZ')}&sp=r&sig=test"

    def put(self, blob_path: str, data: bytes) -> None:
        self.files[blob_path] = data

    def get(self, blob_path: str) -> bytes | None:
        return self.files.get(blob_path)


def default_blobs() -> AutoApplyBlobStore:
    from app.config import get_settings

    settings = get_settings()
    if not settings.cosmos_connection_string:
        return InMemoryBlobStore()
    return InMemoryBlobStore()

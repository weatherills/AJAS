"""Blob SAS helpers for review job/resume artifacts.

SAS URLs are generated at read time (10-minute expiry) and never stored.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import parse_qs, urlparse

from app.config import get_settings
from app.review.constants import SAS_TTL_MINUTES


class ReviewBlobStore(Protocol):
    def sas_url(self, blob_path: str, *, minutes: int = SAS_TTL_MINUTES) -> str: ...


class InMemoryBlobStore:
    def sas_url(self, blob_path: str, *, minutes: int = SAS_TTL_MINUTES) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return f"https://blob.local/{blob_path}?se={expiry.strftime('%Y-%m-%dT%H:%M:%SZ')}&sp=r&sig=test"


class AzureReviewBlobStore:
    def __init__(self, client=None, container_name: str | None = None) -> None:
        settings = get_settings()
        self._container_name = container_name or settings.review_blob_container
        if client is None:
            from app.storage.blobs import get_blob_service_client

            client = get_blob_service_client()
        self._container = client.get_container_client(self._container_name)

    def sas_url(self, blob_path: str, *, minutes: int = SAS_TTL_MINUTES) -> str:
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        settings = get_settings()
        account_name, account_key = _account_from_connection_string(settings.blob_connection_string)
        expiry = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        sas = generate_blob_sas(
            account_name=account_name,
            container_name=self._container_name,
            blob_name=blob_path,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry,
        )
        url = self._container.get_blob_client(blob_path).url
        return f"{url}?{sas}"


def default_blobs() -> ReviewBlobStore:
    settings = get_settings()
    if not settings.cosmos_connection_string:
        return InMemoryBlobStore()
    return AzureReviewBlobStore()


def _account_from_connection_string(value: str) -> tuple[str, str]:
    if value == "UseDevelopmentStorage=true":
        return (
            "devstoreaccount1",
            "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==",
        )
    parts = dict(item.split("=", 1) for item in value.split(";") if "=" in item)
    return parts.get("AccountName", ""), parts.get("AccountKey", "")


def sas_is_expired(url: str, *, now: datetime | None = None) -> bool:
    """True when a SAS ``se=`` timestamp is in the past."""
    now = now or datetime.now(timezone.utc)
    se = parse_qs(urlparse(url).query).get("se", [None])[0]
    if not se:
        return False
    stamp = se.replace("Z", "+00:00")
    expiry = datetime.fromisoformat(stamp)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return now >= expiry

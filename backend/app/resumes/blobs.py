"""Blob helpers for original resume files."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import parse_qs, urlparse

from app.config import get_settings


class ResumeBlobStore(Protocol):
    def put(
        self,
        *,
        user_id: str,
        resume_id: str,
        filename: str,
        data: bytes,
        mime_type: str,
    ) -> str: ...

    def get(self, blob_path: str) -> bytes: ...

    def sas_url(self, blob_path: str, *, minutes: int = 10) -> str: ...


class InMemoryBlobStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, *, user_id: str, resume_id: str, filename: str, data: bytes, mime_type: str) -> str:
        path = f"{user_id}/{resume_id}/{filename}"
        self.objects[path] = data
        return path

    def get(self, blob_path: str) -> bytes:
        try:
            return self.objects[blob_path]
        except KeyError as exc:
            raise FileNotFoundError(blob_path) from exc

    def sas_url(self, blob_path: str, *, minutes: int = 10) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return f"https://blob.local/{blob_path}?se={expiry.strftime('%Y-%m-%dT%H:%M:%SZ')}&sp=r&sig=test"


class AzureResumeBlobStore:
    def __init__(self, client=None, container_name: str | None = None) -> None:
        settings = get_settings()
        self._container_name = container_name or settings.resume_blob_container
        if client is None:
            from app.storage.blobs import get_blob_service_client

            client = get_blob_service_client()
        self._service = client
        self._container = client.get_container_client(self._container_name)

    def put(self, *, user_id: str, resume_id: str, filename: str, data: bytes, mime_type: str) -> str:
        path = f"{user_id}/{resume_id}/{filename}"
        try:
            self._container.create_container()
        except Exception:
            pass
        self._container.upload_blob(name=path, data=data, overwrite=True, content_type=mime_type)
        return path

    def get(self, blob_path: str) -> bytes:
        return self._container.download_blob(blob_path).readall()

    def sas_url(self, blob_path: str, *, minutes: int = 10) -> str:
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

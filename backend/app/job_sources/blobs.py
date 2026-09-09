"""Blob store for raw job posting payloads."""

from __future__ import annotations

from typing import Protocol


class BlobStore(Protocol):
    def put(self, path: str, data: bytes, content_type: str = "application/json") -> str: ...


class InMemoryBlobStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, path: str, data: bytes, content_type: str = "application/json") -> str:
        self.objects[path] = data
        return f"memory://{path}"


class AzureBlobStore:
    def __init__(self, container: str) -> None:
        self.container = container

    def put(self, path: str, data: bytes, content_type: str = "application/json") -> str:
        from app.storage.blobs import get_blob_service_client

        service = get_blob_service_client()
        client = service.get_container_client(self.container)
        try:
            client.create_container()
        except Exception:
            pass
        blob = client.get_blob_client(path)
        blob.upload_blob(data, overwrite=True, content_type=content_type)
        return blob.url


def default_blobs() -> BlobStore:
    from app.config import get_settings

    settings = get_settings()
    if not settings.cosmos_connection_string:
        return InMemoryBlobStore()
    return AzureBlobStore(settings.job_raw_blob_container)

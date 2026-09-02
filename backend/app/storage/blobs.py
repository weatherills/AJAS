"""Blob Storage client factory (resumes, raw postings, artifacts)."""
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    from azure.storage.blob import BlobServiceClient


@lru_cache
def get_blob_service_client() -> "BlobServiceClient":
    """Return a cached Blob service client built from configuration."""
    from azure.storage.blob import BlobServiceClient

    settings = get_settings()
    if not settings.blob_connection_string:
        raise RuntimeError("BLOB_CONNECTION_STRING is not configured.")
    return BlobServiceClient.from_connection_string(settings.blob_connection_string)

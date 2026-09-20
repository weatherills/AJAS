"""Blob Storage client factory (resumes, raw postings, artifacts)."""
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings
from app.storage.identity import resolve_blob_auth

if TYPE_CHECKING:  # pragma: no cover
    from azure.storage.blob import BlobServiceClient


@lru_cache
def get_blob_service_client() -> "BlobServiceClient":
    """Return a cached Blob service client built from configuration."""
    from azure.storage.blob import BlobServiceClient

    settings = get_settings()
    auth = resolve_blob_auth(settings)
    if auth["mode"] == "connection_string":
        return BlobServiceClient.from_connection_string(settings.blob_connection_string)
    if auth["mode"] == "aad":
        from app.storage.identity import default_azure_credential

        return BlobServiceClient(account_url=settings.blob_account_url, credential=default_azure_credential())
    raise RuntimeError("BLOB_CONNECTION_STRING or BLOB_ACCOUNT_URL is not configured.")

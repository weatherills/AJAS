"""Cosmos DB client factory.

Uses a connection string (local/CI), an emulator key, or DefaultAzureCredential
against COSMOS_ENDPOINT. Secrets are never logged.
"""
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings
from app.storage.identity import resolve_cosmos_auth

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from azure.cosmos import CosmosClient, DatabaseProxy


@lru_cache
def get_cosmos_client() -> "CosmosClient":
    """Return a cached Cosmos client built from configuration."""
    from azure.cosmos import CosmosClient

    settings = get_settings()
    auth = resolve_cosmos_auth(settings)
    if auth["mode"] == "connection_string":
        return CosmosClient.from_connection_string(settings.cosmos_connection_string)
    if auth["mode"] == "key":
        return CosmosClient(url=settings.cosmos_endpoint, credential=settings.cosmos_key)
    if auth["mode"] == "aad":
        from app.storage.identity import default_azure_credential

        return CosmosClient(url=settings.cosmos_endpoint, credential=default_azure_credential())
    raise RuntimeError("Cosmos is not configured. Set COSMOS_CONNECTION_STRING or COSMOS_ENDPOINT.")


def get_database() -> "DatabaseProxy":
    """Return the configured application database proxy."""
    return get_cosmos_client().get_database_client(get_settings().cosmos_database)

"""Cosmos DB client factory.

Uses a connection string (local/CI), an emulator key, or DefaultAzureCredential
against COSMOS_ENDPOINT. Secrets are never logged.
"""
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from app.config import Settings, get_settings
from app.storage.consistency import container_consistency
from app.storage.identity import resolve_cosmos_auth
from app.storage.replication import preferred_regions

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from azure.cosmos import CosmosClient, DatabaseProxy


def cosmos_client_kwargs(settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    kwargs: dict[str, Any] = {
        "consistency_level": container_consistency("matches", cfg),
    }
    regions = preferred_regions(cfg)
    if regions:
        kwargs["preferred_locations"] = regions
    return kwargs


def reset_cosmos_client() -> None:
    get_cosmos_client.cache_clear()


@lru_cache
def get_cosmos_client() -> "CosmosClient":
    """Return a cached Cosmos client built from configuration."""
    from azure.cosmos import CosmosClient

    settings = get_settings()
    auth = resolve_cosmos_auth(settings)
    extra = cosmos_client_kwargs(settings)
    try:
        if auth["mode"] == "connection_string":
            return CosmosClient.from_connection_string(settings.cosmos_connection_string, **extra)
        if auth["mode"] == "key":
            return CosmosClient(url=settings.cosmos_endpoint, credential=settings.cosmos_key, **extra)
        if auth["mode"] == "aad":
            from app.storage.identity import default_azure_credential

            return CosmosClient(url=settings.cosmos_endpoint, credential=default_azure_credential(), **extra)
    except TypeError:
        extra = {key: value for key, value in extra.items() if key == "consistency_level"}
        if auth["mode"] == "connection_string":
            return CosmosClient.from_connection_string(settings.cosmos_connection_string, **extra)
        if auth["mode"] == "key":
            return CosmosClient(url=settings.cosmos_endpoint, credential=settings.cosmos_key, **extra)
        if auth["mode"] == "aad":
            from app.storage.identity import default_azure_credential

            return CosmosClient(url=settings.cosmos_endpoint, credential=default_azure_credential(), **extra)
    raise RuntimeError("Cosmos is not configured. Set COSMOS_CONNECTION_STRING or COSMOS_ENDPOINT.")


def get_database() -> "DatabaseProxy":
    """Return the configured application database proxy."""
    return get_cosmos_client().get_database_client(get_settings().cosmos_database)

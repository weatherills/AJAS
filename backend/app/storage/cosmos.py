"""Cosmos DB client factory.

Thin, lazily-constructed accessor so feature code shares a single configured
client. Containers and query logic are added per feature (resumes, job_postings,
matches, run selections, ...).
"""
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from azure.cosmos import CosmosClient, DatabaseProxy


@lru_cache
def get_cosmos_client() -> "CosmosClient":
    """Return a cached Cosmos client built from configuration."""
    from azure.cosmos import CosmosClient

    settings = get_settings()
    if not settings.cosmos_connection_string:
        raise RuntimeError("COSMOS_CONNECTION_STRING is not configured.")
    return CosmosClient.from_connection_string(settings.cosmos_connection_string)


def get_database() -> "DatabaseProxy":
    """Return the configured application database proxy."""
    return get_cosmos_client().get_database_client(get_settings().cosmos_database)

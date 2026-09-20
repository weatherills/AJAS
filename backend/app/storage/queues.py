"""Storage Queue client factory (async pipelines: parse, crawl, match, ...)."""
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings
from app.storage.identity import resolve_queue_auth

if TYPE_CHECKING:  # pragma: no cover
    from azure.storage.queue import QueueClient


def get_queue_client(queue_name: str) -> "QueueClient":
    """Return a Queue client for ``queue_name`` built from configuration."""
    settings = get_settings()
    auth = resolve_queue_auth(settings)
    if auth["mode"] == "connection_string":
        return _queue_client(settings.queue_connection_string, queue_name)
    if auth["mode"] == "aad":
        from azure.storage.queue import QueueClient

        from app.storage.identity import default_azure_credential

        return QueueClient(
            account_url=settings.queue_account_url,
            queue_name=queue_name,
            credential=default_azure_credential(),
        )
    raise RuntimeError("QUEUE_CONNECTION_STRING or QUEUE_ACCOUNT_URL is not configured.")


@lru_cache
def _queue_client(connection_string: str, queue_name: str) -> "QueueClient":
    from azure.storage.queue import QueueClient

    return QueueClient.from_connection_string(connection_string, queue_name)

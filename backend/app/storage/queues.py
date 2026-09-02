"""Storage Queue client factory (async pipelines: parse, crawl, match, ...)."""
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:  # pragma: no cover
    from azure.storage.queue import QueueClient


def get_queue_client(queue_name: str) -> "QueueClient":
    """Return a Queue client for ``queue_name`` built from configuration."""
    settings = get_settings()
    if not settings.queue_connection_string:
        raise RuntimeError("QUEUE_CONNECTION_STRING is not configured.")
    return _queue_client(settings.queue_connection_string, queue_name)


@lru_cache
def _queue_client(connection_string: str, queue_name: str) -> "QueueClient":
    from azure.storage.queue import QueueClient

    return QueueClient.from_connection_string(connection_string, queue_name)

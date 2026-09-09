"""In-process parse-job queue used when Azure Storage Queues are unavailable."""

from __future__ import annotations

import json
from typing import Callable, Protocol

from app.config import get_settings


class ParseQueue(Protocol):
    def enqueue(self, message: dict) -> None: ...


class InMemoryParseQueue:
    def __init__(self, handler: Callable[[dict], None] | None = None) -> None:
        self.messages: list[dict] = []
        self.handler = handler

    def enqueue(self, message: dict) -> None:
        self.messages.append(dict(message))
        if self.handler:
            self.handler(dict(message))


class AzureParseQueue:
    def enqueue(self, message: dict) -> None:
        from azure.storage.queue import QueueClient

        settings = get_settings()
        client = QueueClient.from_connection_string(
            settings.queue_connection_string,
            settings.resume_parse_queue,
        )
        try:
            client.create_queue()
        except Exception:
            pass
        client.send_message(json.dumps(message))


def default_queue() -> ParseQueue:
    settings = get_settings()
    if settings.queue_connection_string:
        return AzureParseQueue()
    return InMemoryParseQueue()

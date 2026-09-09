"""Queues used by Auto-Apply workers."""

from __future__ import annotations

import json
import time
from typing import Protocol


class JobQueue(Protocol):
    def enqueue(self, queue_name: str, message: dict) -> None: ...


class InMemoryJobQueue:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    def enqueue(self, queue_name: str, message: dict) -> None:
        self.messages.append((queue_name, dict(message)))

    def of(self, queue_name: str) -> list[dict]:
        return [body for name, body in self.messages if name == queue_name]


class AzureJobQueue:
    def enqueue(self, queue_name: str, message: dict) -> None:
        from app.storage.queues import get_queue_client

        client = get_queue_client(queue_name)
        last_error: Exception | None = None
        delay = 0.05
        payload = json.dumps(message, default=str)
        for _ in range(4):
            try:
                try:
                    client.create_queue()
                except Exception:
                    pass
                client.send_message(payload)
                return
            except Exception as exc:
                last_error = exc
                time.sleep(delay)
                delay *= 2
        assert last_error is not None
        raise last_error


def default_queue() -> JobQueue:
    from app.config import get_settings

    settings = get_settings()
    if not settings.cosmos_connection_string or not settings.queue_connection_string:
        return InMemoryJobQueue()
    return AzureJobQueue()

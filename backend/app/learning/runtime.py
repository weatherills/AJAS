"""Process-wide LearningService used by HTTP, queue, and timer triggers."""

from __future__ import annotations

from app.learning.service import LearningService

_service: LearningService | None = None


def get_service() -> LearningService:
    global _service
    if _service is None:
        from app.config import get_settings
        from app.learning.queues import InMemoryJobQueue, default_queue
        from app.learning.store import get_learning_store

        settings = get_settings()
        local_mode = not (settings.cosmos_connection_string or "").strip()
        queue = InMemoryJobQueue() if local_mode else default_queue()
        _service = LearningService(store=get_learning_store(), queue=queue, local_mode=local_mode)
    return _service


def try_get_service() -> LearningService | None:
    return _service


def set_service(service: LearningService | None) -> None:
    global _service
    _service = service

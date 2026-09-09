"""Process-wide MatchingService used by HTTP and queue triggers."""

from __future__ import annotations

from app.matching.service import MatchingService

_service: MatchingService | None = None


def get_service() -> MatchingService:
    global _service
    if _service is None:
        from app.config import get_settings
        from app.matching.embedder import default_embedder
        from app.matching.explain import default_explainer
        from app.matching.queues import InMemoryJobQueue, default_queue
        from app.matching.store import get_matching_store
        from app.matching.texts import StackedTextLoader

        settings = get_settings()
        use_local_queue = not (settings.cosmos_connection_string or "").strip()
        queue = InMemoryJobQueue() if use_local_queue else default_queue()
        _service = MatchingService(
            store=get_matching_store(),
            queue=queue,
            embedder=default_embedder(),
            explainer=default_explainer(),
            text_loader=StackedTextLoader(),
        )
    return _service


def set_service(service: MatchingService | None) -> None:
    global _service
    _service = service

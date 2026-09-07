"""Process-wide MatchingService used by HTTP and queue triggers."""

from __future__ import annotations

from app.matching.service import MatchingService

_service: MatchingService | None = None


def get_service() -> MatchingService:
    global _service
    if _service is None:
        from app.matching.embedder import default_embedder
        from app.matching.explain import default_explainer
        from app.matching.queues import default_queue
        from app.matching.store import get_matching_store
        from app.matching.texts import NotFoundTextLoader

        _service = MatchingService(
            store=get_matching_store(),
            queue=default_queue(),
            embedder=default_embedder(),
            explainer=default_explainer(),
            text_loader=NotFoundTextLoader(),
        )
    return _service


def set_service(service: MatchingService | None) -> None:
    global _service
    _service = service

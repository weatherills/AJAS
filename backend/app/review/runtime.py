"""Process-wide ReviewService used by HTTP and queue triggers."""

from __future__ import annotations

from app.review.service import ReviewService

_service: ReviewService | None = None


def get_service() -> ReviewService:
    global _service
    if _service is None:
        from app.review.blobs import default_blobs
        from app.review.queues import default_queue
        from app.review.store import get_review_store

        _service = ReviewService(
            store=get_review_store(),
            queue=default_queue(),
            blobs=default_blobs(),
        )
    return _service


def set_service(service: ReviewService | None) -> None:
    global _service
    _service = service

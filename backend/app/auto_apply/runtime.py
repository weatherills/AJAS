"""Process-wide AutoApplyService used by HTTP and queue triggers."""

from __future__ import annotations

from app.auto_apply.service import AutoApplyService

_service: AutoApplyService | None = None


def get_service() -> AutoApplyService:
    global _service
    if _service is None:
        from app.auto_apply.blobs import default_blobs
        from app.auto_apply.queues import default_queue
        from app.auto_apply.store import get_auto_apply_store

        _service = AutoApplyService(
            store=get_auto_apply_store(),
            queue=default_queue(),
            blobs=default_blobs(),
        )
    return _service


def set_service(service: AutoApplyService | None) -> None:
    global _service
    _service = service

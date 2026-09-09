"""Process-wide EmailService used by HTTP, queue, and timer triggers."""

from __future__ import annotations

from app.mail.service import EmailService

_service: EmailService | None = None


def get_service() -> EmailService:
    global _service
    if _service is None:
        from app.config import get_settings
        from app.mail.graph import default_graph_client
        from app.mail.queues import InMemoryJobQueue, default_queue
        from app.mail.store import get_email_store

        settings = get_settings()
        local_mode = not (settings.cosmos_connection_string or "").strip()
        queue = InMemoryJobQueue() if local_mode else default_queue()
        _service = EmailService(
            store=get_email_store(),
            queue=queue,
            graph=default_graph_client(),
            local_mode=local_mode,
        )
    return _service


def set_service(service: EmailService | None) -> None:
    global _service
    _service = service

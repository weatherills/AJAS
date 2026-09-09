"""Process-wide CrawlService used by HTTP, timer, and queue triggers."""

from __future__ import annotations

from app.job_sources.service import CrawlService

_service: CrawlService | None = None


def get_service() -> CrawlService:
    global _service
    if _service is None:
        from app.job_sources.blobs import default_blobs
        from app.job_sources.http import UrllibFetcher
        from app.job_sources.queues import default_queue
        from app.job_sources.store import get_job_source_store

        _service = CrawlService(
            store=get_job_source_store(),
            queue=default_queue(),
            blobs=default_blobs(),
            fetcher=UrllibFetcher(),
        )
    return _service


def set_service(service: CrawlService | None) -> None:
    global _service
    _service = service

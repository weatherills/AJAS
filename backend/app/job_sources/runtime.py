"""Process-wide CrawlService used by HTTP, timer, and queue triggers."""

from __future__ import annotations

from app.job_sources.service import CrawlService

_service: CrawlService | None = None


def get_service() -> CrawlService:
    global _service
    if _service is None:
        from app.config import get_settings
        from app.job_sources.blobs import default_blobs
        from app.job_sources.feed import seed_demo_feed
        from app.job_sources.http import UrllibFetcher
        from app.job_sources.memory import InMemoryJobSourceStore
        from app.job_sources.queues import InMemoryJobQueue, default_queue
        from app.job_sources.store import get_job_source_store

        settings = get_settings()
        store = get_job_source_store()
        use_local_queue = not (settings.cosmos_connection_string or "").strip()
        queue = InMemoryJobQueue() if use_local_queue else default_queue()
        if isinstance(store, InMemoryJobSourceStore):
            seed_demo_feed(store)
        _service = CrawlService(
            store=store,
            queue=queue,
            blobs=default_blobs(),
            fetcher=UrllibFetcher(),
        )
    return _service


def set_service(service: CrawlService | None) -> None:
    global _service
    _service = service


def try_get_service() -> CrawlService | None:
    return _service


def tenant_counts_or_none() -> dict[str, int] | None:
    """Greenhouse/Lever tenant counts when crawl is wired; None if not."""
    service = try_get_service()
    if service is None:
        return None
    return {
        "greenhouse": len(service.store.list_tenants("greenhouse")),
        "lever": len(service.store.list_tenants("lever")),
    }

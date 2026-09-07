"""Job source store protocol and factory."""

from __future__ import annotations

from typing import Protocol

from app.job_sources.models import (
    CrawlSchedule,
    FetchCursor,
    FetchRequest,
    JobPostingCanonical,
    JobPostingLink,
    JobPostingRaw,
    JobSource,
    SourceFetchRun,
    SourceRateLimit,
    SourceTenant,
)


class JobSourceStore(Protocol):
    def seed_sources(self) -> list[JobSource]: ...

    def list_sources(self) -> list[JobSource]: ...

    def upsert_tenant(
        self,
        source_id: str,
        tenant_key: str,
        *,
        config: dict | None = None,
        enabled: bool = True,
    ) -> SourceTenant: ...

    def get_tenant(self, tenant_id: str) -> SourceTenant: ...

    def list_tenants(self, source_id: str | None = None) -> list[SourceTenant]: ...

    def start_run(self, tenant_id: str) -> SourceFetchRun: ...

    def record_request(self, tenant_id: str, run_id: str, **kwargs) -> FetchRequest: ...

    def finish_run(self, run_id: str, *, status: str, error_summary: str | None = None) -> SourceFetchRun: ...

    def save_cursor(self, tenant_id: str, endpoint: str, cursor: str | None) -> FetchCursor: ...

    def get_cursor(self, tenant_id: str, endpoint: str) -> FetchCursor | None: ...

    def reset_cursor(self, tenant_id: str, endpoint: str, *, run_id: str | None = None) -> FetchCursor: ...

    def ingest_raw(self, tenant_id: str, **kwargs) -> tuple[JobPostingRaw, str]: ...

    def close_posting(self, tenant_id: str, source_posting_id: str) -> JobPostingRaw: ...

    def consume_rate_limit(self, tenant_id: str, *, cost: float = 1.0, now: str | None = None) -> SourceRateLimit: ...

    def set_backoff(self, tenant_id: str, *, until: str, request_id: str | None = None) -> SourceRateLimit: ...

    def due_schedules(self, *, now: str | None = None) -> list[CrawlSchedule]: ...

    def list_raw(self, tenant_id: str, *, current_only: bool = False) -> list[JobPostingRaw]: ...

    def list_canonical(self) -> list[JobPostingCanonical]: ...

    def list_links(self, *, raw_id: str | None = None, canonical_id: str | None = None) -> list[JobPostingLink]: ...

    def list_requests(self, run_id: str) -> list[FetchRequest]: ...

    def get_run(self, run_id: str) -> SourceFetchRun: ...

    def get_schedule(self, tenant_id: str) -> CrawlSchedule: ...

    def get_rate_limit(self, tenant_id: str) -> SourceRateLimit: ...

    def set_schedule_paused(self, tenant_id: str, paused: bool) -> CrawlSchedule: ...


def get_job_source_store() -> JobSourceStore:
    from app.config import get_settings
    from app.job_sources.memory import InMemoryJobSourceStore

    settings = get_settings()
    if not settings.cosmos_connection_string:
        return InMemoryJobSourceStore()
    from app.job_sources.cosmos_store import CosmosJobSourceStore
    from app.storage.cosmos import get_database

    return CosmosJobSourceStore(get_database())

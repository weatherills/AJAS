"""Cosmos DB implementation of JobSourceStore."""

from __future__ import annotations

from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.job_sources.constants import (
    CANONICAL_CONTAINER,
    CURSORS_CONTAINER,
    LINKS_CONTAINER,
    RATE_LIMITS_CONTAINER,
    RAW_CONTAINER,
    REQUESTS_CONTAINER,
    RUNS_CONTAINER,
    SCHEDULES_CONTAINER,
    SOURCES_CONTAINER,
    TENANTS_CONTAINER,
)
from app.job_sources.memory import InMemoryJobSourceStore
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


class CosmosJobSourceStore:
    """Persists job-source documents using the in-memory rule engine."""

    def __init__(self, database: Any) -> None:
        self._sources = database.get_container_client(SOURCES_CONTAINER)
        self._tenants = database.get_container_client(TENANTS_CONTAINER)
        self._runs = database.get_container_client(RUNS_CONTAINER)
        self._requests = database.get_container_client(REQUESTS_CONTAINER)
        self._cursors = database.get_container_client(CURSORS_CONTAINER)
        self._raw = database.get_container_client(RAW_CONTAINER)
        self._canonical = database.get_container_client(CANONICAL_CONTAINER)
        self._links = database.get_container_client(LINKS_CONTAINER)
        self._limits = database.get_container_client(RATE_LIMITS_CONTAINER)
        self._schedules = database.get_container_client(SCHEDULES_CONTAINER)

    def seed_sources(self) -> list[JobSource]:
        working = self._hydrate()
        rows = working.seed_sources()
        self._persist_working(working)
        return rows

    def list_sources(self) -> list[JobSource]:
        return self._hydrate().list_sources()

    def upsert_tenant(self, source_id: str, tenant_key: str, **kwargs: Any) -> SourceTenant:
        working = self._hydrate()
        saved = working.upsert_tenant(source_id, tenant_key, **kwargs)
        self._persist_working(working)
        return saved

    def get_tenant(self, tenant_id: str) -> SourceTenant:
        return self._hydrate().get_tenant(tenant_id)

    def list_tenants(self, source_id: str | None = None) -> list[SourceTenant]:
        return self._hydrate().list_tenants(source_id)

    def start_run(self, tenant_id: str) -> SourceFetchRun:
        working = self._hydrate()
        saved = working.start_run(tenant_id)
        self._persist_working(working)
        return saved

    def record_request(self, tenant_id: str, run_id: str, **kwargs: Any) -> FetchRequest:
        working = self._hydrate()
        saved = working.record_request(tenant_id, run_id, **kwargs)
        self._persist_working(working)
        return saved

    def finish_run(self, run_id: str, *, status: str, error_summary: str | None = None) -> SourceFetchRun:
        working = self._hydrate()
        saved = working.finish_run(run_id, status=status, error_summary=error_summary)
        self._persist_working(working)
        return saved

    def save_cursor(self, tenant_id: str, endpoint: str, cursor: str | None) -> FetchCursor:
        working = self._hydrate()
        saved = working.save_cursor(tenant_id, endpoint, cursor)
        self._persist_working(working)
        return saved

    def get_cursor(self, tenant_id: str, endpoint: str) -> FetchCursor | None:
        return self._hydrate().get_cursor(tenant_id, endpoint)

    def reset_cursor(self, tenant_id: str, endpoint: str, *, run_id: str | None = None) -> FetchCursor:
        working = self._hydrate()
        saved = working.reset_cursor(tenant_id, endpoint, run_id=run_id)
        self._persist_working(working)
        return saved

    def ingest_raw(self, tenant_id: str, **kwargs: Any) -> tuple[JobPostingRaw, str]:
        working = self._hydrate()
        saved = working.ingest_raw(tenant_id, **kwargs)
        self._persist_working(working)
        return saved

    def close_posting(self, tenant_id: str, source_posting_id: str) -> JobPostingRaw:
        working = self._hydrate()
        saved = working.close_posting(tenant_id, source_posting_id)
        self._persist_working(working)
        return saved

    def consume_rate_limit(self, tenant_id: str, **kwargs: Any) -> SourceRateLimit:
        working = self._hydrate()
        saved = working.consume_rate_limit(tenant_id, **kwargs)
        self._persist_working(working)
        return saved

    def set_backoff(self, tenant_id: str, **kwargs: Any) -> SourceRateLimit:
        working = self._hydrate()
        saved = working.set_backoff(tenant_id, **kwargs)
        self._persist_working(working)
        return saved

    def due_schedules(self, *, now: str | None = None) -> list[CrawlSchedule]:
        return self._hydrate().due_schedules(now=now)

    def list_raw(self, tenant_id: str, *, current_only: bool = False) -> list[JobPostingRaw]:
        return self._hydrate().list_raw(tenant_id, current_only=current_only)

    def list_canonical(self) -> list[JobPostingCanonical]:
        return self._hydrate().list_canonical()

    def list_links(self, *, raw_id: str | None = None, canonical_id: str | None = None) -> list[JobPostingLink]:
        return self._hydrate().list_links(raw_id=raw_id, canonical_id=canonical_id)

    def list_requests(self, run_id: str) -> list[FetchRequest]:
        return self._hydrate().list_requests(run_id)

    def get_run(self, run_id: str) -> SourceFetchRun:
        return self._hydrate().get_run(run_id)

    def get_schedule(self, tenant_id: str) -> CrawlSchedule:
        return self._hydrate().get_schedule(tenant_id)

    def get_rate_limit(self, tenant_id: str) -> SourceRateLimit:
        return self._hydrate().get_rate_limit(tenant_id)

    def set_schedule_paused(self, tenant_id: str, paused: bool) -> CrawlSchedule:
        working = self._hydrate()
        saved = working.set_schedule_paused(tenant_id, paused)
        self._persist_working(working)
        return saved

    def _all_items(self, client: Any) -> list[dict]:
        try:
            return list(client.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))
        except TypeError:
            return list(client.query_items(query="SELECT * FROM c"))

    def _hydrate(self) -> InMemoryJobSourceStore:
        working = InMemoryJobSourceStore(seed=False)
        working._sources = {row.id: row for row in (JobSource.model_validate(i) for i in self._all_items(self._sources))}
        working._tenants = {row.id: row for row in (SourceTenant.model_validate(i) for i in self._all_items(self._tenants))}
        working._runs = {row.id: row for row in (SourceFetchRun.model_validate(i) for i in self._all_items(self._runs))}
        working._requests = {row.id: row for row in (FetchRequest.model_validate(i) for i in self._all_items(self._requests))}
        working._cursors = {row.id: row for row in (FetchCursor.model_validate(i) for i in self._all_items(self._cursors))}
        working._raw = {row.id: row for row in (JobPostingRaw.model_validate(i) for i in self._all_items(self._raw))}
        working._canonical = {
            row.id: row for row in (JobPostingCanonical.model_validate(i) for i in self._all_items(self._canonical))
        }
        working._links = {row.id: row for row in (JobPostingLink.model_validate(i) for i in self._all_items(self._links))}
        working._limits = {
            row.id: row for row in (SourceRateLimit.model_validate(i) for i in self._all_items(self._limits))
        }
        working._schedules = {
            row.id: row for row in (CrawlSchedule.model_validate(i) for i in self._all_items(self._schedules))
        }
        return working

    def _upsert(self, client: Any, payload: dict) -> None:
        try:
            client.replace_item(item=payload["id"], body=payload)
        except CosmosResourceNotFoundError:
            client.create_item(body=payload)

    def _persist_working(self, working: InMemoryJobSourceStore) -> None:
        for row in working._sources.values():
            self._upsert(self._sources, row.model_dump())
        for row in working._tenants.values():
            self._upsert(self._tenants, row.model_dump())
        for row in working._runs.values():
            self._upsert(self._runs, row.model_dump())
        for row in working._requests.values():
            self._upsert(self._requests, row.model_dump())
        for row in working._cursors.values():
            self._upsert(self._cursors, row.model_dump())
        for row in working._raw.values():
            self._upsert(self._raw, row.model_dump())
        for row in working._canonical.values():
            self._upsert(self._canonical, row.model_dump())
        for row in working._links.values():
            self._upsert(self._links, row.model_dump())
        for row in working._limits.values():
            self._upsert(self._limits, row.model_dump())
        for row in working._schedules.values():
            self._upsert(self._schedules, row.model_dump())

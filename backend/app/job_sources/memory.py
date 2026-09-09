"""In-memory JobSourceStore — rule engine for the Database PRD."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from random import Random

from app.job_sources.constants import (
    DEFAULT_BURST,
    DEFAULT_CRAWL_INTERVAL_SECONDS,
    DEFAULT_TOKENS_PER_MIN,
    LISTING_STATES,
    RUN_STATUSES,
    SEEDED_SOURCES,
)
from app.job_sources.errors import (
    JobSourceConflictError,
    JobSourceNotFoundError,
    JobSourceRateLimitedError,
    JobSourceValidationError,
)
from app.job_sources.keys import (
    canonical_key,
    dedupe_hash,
    parse_ts,
    response_hash,
    utc_now,
)
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
    new_id,
)


class InMemoryJobSourceStore:
    def __init__(self, *, seed: bool = True, rng: Random | None = None) -> None:
        self._sources: dict[str, JobSource] = {}
        self._tenants: dict[str, SourceTenant] = {}
        self._runs: dict[str, SourceFetchRun] = {}
        self._requests: dict[str, FetchRequest] = {}
        self._cursors: dict[str, FetchCursor] = {}
        self._raw: dict[str, JobPostingRaw] = {}
        self._canonical: dict[str, JobPostingCanonical] = {}
        self._links: dict[str, JobPostingLink] = {}
        self._limits: dict[str, SourceRateLimit] = {}
        self._schedules: dict[str, CrawlSchedule] = {}
        self._rng = rng or Random(0)
        if seed:
            self.seed_sources()

    def seed_sources(self) -> list[JobSource]:
        now = utc_now()
        for source_id, name in SEEDED_SOURCES:
            if source_id not in self._sources:
                self._sources[source_id] = JobSource(
                    id=source_id, type=source_id, name=name, created_at=now, updated_at=now  # type: ignore[arg-type]
                )
        return [deepcopy(item) for item in self._sources.values()]

    def list_sources(self) -> list[JobSource]:
        return [deepcopy(item) for item in self._sources.values()]

    def upsert_tenant(
        self,
        source_id: str,
        tenant_key: str,
        *,
        config: dict | None = None,
        enabled: bool = True,
    ) -> SourceTenant:
        if source_id not in self._sources:
            raise JobSourceNotFoundError(source_id)
        if not tenant_key or not tenant_key.strip():
            raise JobSourceValidationError("tenant_key is required", path="tenant_key")
        key = tenant_key.strip()
        for existing in self._tenants.values():
            if existing.source_id == source_id and existing.tenant_key == key:
                existing.config = dict(config or existing.config)
                existing.enabled = enabled
                existing.updated_at = utc_now()
                self._ensure_ops(existing.id)
                return deepcopy(existing)
        now = utc_now()
        tenant = SourceTenant(
            source_id=source_id,
            tenant_key=key,
            config=dict(config or {}),
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )
        self._tenants[tenant.id] = tenant
        self._ensure_ops(tenant.id)
        return deepcopy(tenant)

    def get_tenant(self, tenant_id: str) -> SourceTenant:
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            raise JobSourceNotFoundError(tenant_id)
        return deepcopy(tenant)

    def list_tenants(self, source_id: str | None = None) -> list[SourceTenant]:
        rows = list(self._tenants.values())
        if source_id:
            rows = [item for item in rows if item.source_id == source_id]
        return [deepcopy(item) for item in rows]

    def start_run(self, tenant_id: str, *, status: str = "running") -> SourceFetchRun:
        self.get_tenant(tenant_id)
        if status not in RUN_STATUSES:
            raise JobSourceValidationError(f"invalid run status {status}", path="status")
        now = utc_now()
        run = SourceFetchRun(
            source_tenant_id=tenant_id,
            status=status,  # type: ignore[arg-type]
            started_at=now if status == "running" else None,
            created_at=now,
            updated_at=now,
        )
        self._runs[run.id] = run
        return deepcopy(run)

    def set_run_status(self, run_id: str, status: str) -> SourceFetchRun:
        if status not in RUN_STATUSES:
            raise JobSourceValidationError(f"invalid run status {status}", path="status")
        run = self._require_run(run_id)
        now = utc_now()
        run.status = status  # type: ignore[assignment]
        if status == "running" and not run.started_at:
            run.started_at = now
        run.updated_at = now
        return deepcopy(run)

    def set_run_job_counts(
        self, run_id: str, *, expected: int | None = None, completed_delta: int = 0
    ) -> SourceFetchRun:
        run = self._require_run(run_id)
        if expected is not None:
            run.expected_count = expected
        run.completed_count += completed_delta
        run.updated_at = utc_now()
        return deepcopy(run)

    def list_runs(self, tenant_id: str) -> list[SourceFetchRun]:
        rows = [item for item in self._runs.values() if item.source_tenant_id == tenant_id]
        rows.sort(key=lambda item: item.created_at)
        return [deepcopy(item) for item in rows]

    def record_request(
        self,
        tenant_id: str,
        run_id: str,
        *,
        endpoint: str,
        url: str,
        status_code: int | None = None,
        retry_count: int = 0,
        backoff_ms: int = 0,
        rate_limited: bool = False,
        error: str | None = None,
    ) -> FetchRequest:
        run = self._require_run(run_id)
        if run.source_tenant_id != tenant_id:
            raise JobSourceValidationError("run does not belong to tenant", path="run_id")
        now = utc_now()
        row = FetchRequest(
            source_tenant_id=tenant_id,
            run_id=run_id,
            endpoint=endpoint,
            url=url,
            status_code=status_code,
            retry_count=retry_count,
            backoff_ms=backoff_ms,
            rate_limited=rate_limited,
            error=error,
            request_ts=now,
            created_at=now,
        )
        self._requests[row.id] = row
        if status_code and status_code >= 400:
            run.error_count += 1
            run.updated_at = now
        return deepcopy(row)

    def finish_run(self, run_id: str, *, status: str, error_summary: str | None = None) -> SourceFetchRun:
        if status not in RUN_STATUSES:
            raise JobSourceValidationError(f"invalid run status {status}", path="status")
        run = self._require_run(run_id)
        now = utc_now()
        if status == "succeeded" and run.error_count > 0:
            status = "partial_success"
        run.status = status  # type: ignore[assignment]
        run.error_summary = error_summary
        run.finished_at = now
        run.updated_at = now
        self._bump_schedule(run.source_tenant_id, now)
        return deepcopy(run)

    def save_cursor(self, tenant_id: str, endpoint: str, cursor: str | None) -> FetchCursor:
        self.get_tenant(tenant_id)
        now = utc_now()
        row_id = f"{tenant_id}:{endpoint}"
        row = FetchCursor(
            id=row_id,
            source_tenant_id=tenant_id,
            endpoint=endpoint,
            cursor=cursor,
            updated_at=now,
        )
        self._cursors[row_id] = row
        return deepcopy(row)

    def get_cursor(self, tenant_id: str, endpoint: str) -> FetchCursor | None:
        row = self._cursors.get(f"{tenant_id}:{endpoint}")
        return deepcopy(row) if row else None

    def reset_cursor(self, tenant_id: str, endpoint: str, *, run_id: str | None = None) -> FetchCursor:
        cursor = self.save_cursor(tenant_id, endpoint, None)
        if run_id:
            run = self._require_run(run_id)
            run.error_summary = (run.error_summary or "") + f" cursor reset for {endpoint};"
            run.updated_at = utc_now()
        return cursor

    def ingest_raw(
        self,
        tenant_id: str,
        *,
        source_posting_id: str,
        title: str,
        location: str = "",
        employment_type: str = "",
        company: str = "",
        apply_url: str = "",
        body: str = "",
        payload: str,
        listing_state: str = "open",
        content_blob_url: str | None = None,
        namespace: str | None = None,
        run_id: str | None = None,
    ) -> tuple[JobPostingRaw, str]:
        tenant = self.get_tenant(tenant_id)
        if listing_state not in LISTING_STATES:
            raise JobSourceValidationError("invalid listing_state", path="listing_state")
        if not title or not title.strip():
            raise JobSourceValidationError("title is required", path="title")
        if not source_posting_id:
            raise JobSourceValidationError("source_posting_id is required", path="source_posting_id")
        now = utc_now()
        digest = response_hash(payload)
        ns = namespace if namespace is not None else tenant.tenant_key
        key = canonical_key(title=title, location=location, namespace=ns)
        dhash = dedupe_hash(key=key, body=body, employment_type=employment_type)
        current = self._current_raw(tenant_id, source_posting_id)
        latest = current or self._latest_raw(tenant_id, source_posting_id)
        outcome = "created"
        if latest is not None:
            if latest.response_hash == digest and latest.listing_state == listing_state:
                latest.seen_last_at = now
                latest.updated_at = now
                self._raw[latest.id] = latest
                if run_id:
                    self._require_run(run_id).noop_count += 1
                return deepcopy(latest), "unchanged"
            if current is not None:
                current.is_current = False
                current.updated_at = now
            outcome = "updated"
        raw = JobPostingRaw(
            source_tenant_id=tenant_id,
            source_posting_id=source_posting_id,
            title=title.strip(),
            location=location,
            employment_type=employment_type,
            company=company,
            apply_url=apply_url,
            listing_state=listing_state,  # type: ignore[arg-type]
            body=body,
            content_blob_url=content_blob_url,
            response_hash=digest,
            canonical_key=key,
            dedupe_hash=dhash,
            is_current=listing_state != "closed",
            seen_first_at=latest.seen_first_at if latest else now,
            seen_last_at=now,
            created_at=now,
            updated_at=now,
        )
        if listing_state == "closed":
            raw.is_current = False
        self._raw[raw.id] = raw
        self._link_canonical(raw)
        if listing_state == "closed":
            self._refresh_canonical_active(raw.canonical_key)
        if run_id:
            run = self._require_run(run_id)
            run.fetched_count += 1
            if outcome == "created":
                run.upsert_count += 1
            else:
                run.upsert_count += 1
            run.updated_at = now
        return deepcopy(raw), outcome

    def close_posting(self, tenant_id: str, source_posting_id: str) -> JobPostingRaw:
        current = self._current_raw(tenant_id, source_posting_id)
        if current is None:
            raise JobSourceNotFoundError(source_posting_id)
        now = utc_now()
        current.is_current = False
        current.listing_state = "closed"
        current.updated_at = now
        self._raw[current.id] = current
        self._refresh_canonical_active(current.canonical_key)
        return deepcopy(current)

    def consume_rate_limit(self, tenant_id: str, *, cost: float = 1.0, now: str | None = None) -> SourceRateLimit:
        self.get_tenant(tenant_id)
        stamp = now or utc_now()
        limit = self._limits[tenant_id]
        if limit.backoff_until and parse_ts(stamp) < parse_ts(limit.backoff_until):
            raise JobSourceRateLimitedError(f"backoff until {limit.backoff_until}")
        elapsed = (parse_ts(stamp) - parse_ts(limit.window_start)).total_seconds()
        refill = (limit.effective_per_min / 60.0) * max(0.0, elapsed)
        limit.tokens_remaining = min(float(limit.burst), limit.tokens_remaining + refill)
        limit.window_start = stamp
        if limit.tokens_remaining < cost:
            raise JobSourceRateLimitedError("token bucket empty")
        limit.tokens_remaining -= cost
        limit.updated_at = stamp
        return deepcopy(limit)

    def set_backoff(self, tenant_id: str, *, until: str, request_id: str | None = None) -> SourceRateLimit:
        self.get_tenant(tenant_id)
        limit = self._limits[tenant_id]
        limit.backoff_until = until
        limit.updated_at = utc_now()
        if request_id and request_id in self._requests:
            self._requests[request_id].rate_limited = True
        return deepcopy(limit)

    def due_schedules(self, *, now: str | None = None) -> list[CrawlSchedule]:
        stamp = now or utc_now()
        rows = [
            deepcopy(item)
            for item in self._schedules.values()
            if not item.is_paused and parse_ts(item.next_run_after) <= parse_ts(stamp)
        ]
        rows.sort(key=lambda item: item.next_run_after)
        return rows

    def list_raw(self, tenant_id: str, *, current_only: bool = False) -> list[JobPostingRaw]:
        rows = [item for item in self._raw.values() if item.source_tenant_id == tenant_id]
        if current_only:
            rows = [item for item in rows if item.is_current]
        return [deepcopy(item) for item in rows]

    def list_canonical(self) -> list[JobPostingCanonical]:
        return [deepcopy(item) for item in self._canonical.values()]

    def list_links(self, *, raw_id: str | None = None, canonical_id: str | None = None) -> list[JobPostingLink]:
        rows = list(self._links.values())
        if raw_id:
            rows = [item for item in rows if item.raw_id == raw_id]
        if canonical_id:
            rows = [item for item in rows if item.canonical_id == canonical_id]
        return [deepcopy(item) for item in rows]

    def list_requests(self, run_id: str) -> list[FetchRequest]:
        return [deepcopy(item) for item in self._requests.values() if item.run_id == run_id]

    def get_run(self, run_id: str) -> SourceFetchRun:
        return deepcopy(self._require_run(run_id))

    def get_schedule(self, tenant_id: str) -> CrawlSchedule:
        row = self._schedules.get(tenant_id)
        if row is None:
            raise JobSourceNotFoundError(tenant_id)
        return deepcopy(row)

    def get_rate_limit(self, tenant_id: str) -> SourceRateLimit:
        row = self._limits.get(tenant_id)
        if row is None:
            raise JobSourceNotFoundError(tenant_id)
        return deepcopy(row)

    def set_schedule_paused(self, tenant_id: str, paused: bool) -> CrawlSchedule:
        schedule = self._schedules.get(tenant_id)
        if schedule is None:
            raise JobSourceNotFoundError(tenant_id)
        schedule.is_paused = paused
        schedule.updated_at = utc_now()
        return deepcopy(schedule)

    def _ensure_ops(self, tenant_id: str) -> None:
        now = utc_now()
        if tenant_id not in self._limits:
            self._limits[tenant_id] = SourceRateLimit(
                id=tenant_id,
                source_tenant_id=tenant_id,
                effective_per_min=DEFAULT_TOKENS_PER_MIN,
                burst=DEFAULT_BURST,
                tokens_remaining=float(DEFAULT_BURST),
                window_start=now,
                updated_at=now,
            )
        if tenant_id not in self._schedules:
            self._schedules[tenant_id] = CrawlSchedule(
                id=tenant_id,
                source_tenant_id=tenant_id,
                interval_seconds=DEFAULT_CRAWL_INTERVAL_SECONDS,
                next_run_after=now,
                updated_at=now,
            )

    def _require_run(self, run_id: str) -> SourceFetchRun:
        run = self._runs.get(run_id)
        if run is None:
            raise JobSourceNotFoundError(run_id)
        return run

    def _current_raw(self, tenant_id: str, source_posting_id: str) -> JobPostingRaw | None:
        matches = [
            item
            for item in self._raw.values()
            if item.source_tenant_id == tenant_id
            and item.source_posting_id == source_posting_id
            and item.is_current
        ]
        if len(matches) > 1:
            raise JobSourceConflictError("multiple current raw rows for posting")
        return matches[0] if matches else None

    def _latest_raw(self, tenant_id: str, source_posting_id: str) -> JobPostingRaw | None:
        matches = [
            item
            for item in self._raw.values()
            if item.source_tenant_id == tenant_id and item.source_posting_id == source_posting_id
        ]
        if not matches:
            return None
        matches.sort(key=lambda item: (item.seen_last_at, item.created_at), reverse=True)
        return matches[0]

    def _link_canonical(self, raw: JobPostingRaw) -> JobPostingLink:
        now = utc_now()
        existing = next((item for item in self._canonical.values() if item.dedupe_hash == raw.dedupe_hash), None)
        if existing is None:
            existing = next(
                (item for item in self._canonical.values() if item.canonical_key == raw.canonical_key), None
            )
        if existing is None:
            existing = JobPostingCanonical(
                id=new_id(),
                canonical_key=raw.canonical_key,
                dedupe_hash=raw.dedupe_hash,
                title=raw.title,
                location=raw.location,
                employment_type=raw.employment_type,
                is_active=raw.is_current,
                created_at=now,
                updated_at=now,
            )
            self._canonical[existing.id] = existing
            reason = "created"
            confidence = 1.0
        else:
            existing.dedupe_hash = raw.dedupe_hash
            existing.title = raw.title
            existing.location = raw.location
            existing.employment_type = raw.employment_type
            existing.updated_at = now
            if raw.is_current:
                existing.is_active = True
            reason = "merged"
            confidence = 0.9 if existing.canonical_key == raw.canonical_key else 0.7
        for link in self._links.values():
            if link.raw_id == raw.id:
                raise JobSourceConflictError("raw already linked to a canonical posting")
        link = JobPostingLink(
            raw_id=raw.id,
            canonical_id=existing.id,
            confidence=confidence,
            reason=reason,
            created_at=now,
            updated_at=now,
        )
        self._links[link.id] = link
        return deepcopy(link)

    def _refresh_canonical_active(self, canonical_key_value: str) -> None:
        matching = [item for item in self._canonical.values() if item.canonical_key == canonical_key_value]
        for canonical in matching:
            linked_raw_ids = [link.raw_id for link in self._links.values() if link.canonical_id == canonical.id]
            any_current = any(self._raw[raw_id].is_current for raw_id in linked_raw_ids if raw_id in self._raw)
            canonical.is_active = any_current
            canonical.updated_at = utc_now()

    def _bump_schedule(self, tenant_id: str, now: str) -> None:
        schedule = self._schedules.get(tenant_id)
        if schedule is None:
            return
        jitter = self._rng.randint(0, 30)
        nxt = parse_ts(now) + timedelta(seconds=schedule.interval_seconds + jitter)
        schedule.next_run_after = nxt.isoformat().replace("+00:00", "Z")
        schedule.updated_at = now

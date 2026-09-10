"""Job Source Database PRD — schema, constraints, and store behaviors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.job_sources import (
    InMemoryJobSourceStore,
    JobSourceNotFoundError,
    JobSourceRateLimitedError,
    JobSourceValidationError,
    canonical_key,
    container_specs,
    dedupe_hash,
    get_job_source_store,
    response_hash,
)
from app.job_sources.constants import (
    CANONICAL_CONTAINER,
    CANONICAL_PK,
    CURSORS_CONTAINER,
    CURSORS_PK,
    DEFAULT_BURST,
    DEFAULT_CRAWL_INTERVAL_SECONDS,
    LINKS_CONTAINER,
    LINKS_PK,
    RATE_LIMITS_CONTAINER,
    RATE_LIMITS_PK,
    RAW_CONTAINER,
    RAW_PK,
    REQUESTS_CONTAINER,
    REQUESTS_PK,
    RUNS_CONTAINER,
    RUNS_PK,
    SCHEDULES_CONTAINER,
    SCHEDULES_PK,
    SOURCES_CONTAINER,
    SOURCES_PK,
    TENANTS_CONTAINER,
    TENANTS_PK,
)
from app.job_sources.containers import ensure_job_source_containers
from app.job_sources.cosmos_store import CosmosJobSourceStore
from app.job_sources.keys import parse_ts


def _not_found() -> CosmosResourceNotFoundError:
    return CosmosResourceNotFoundError(status_code=404, message="not found")


class FakeContainer:
    def __init__(self, pk_field: str) -> None:
        self.pk_field = pk_field
        self.items: dict[tuple[str, str], dict] = {}

    def create_item(self, body: dict) -> dict:
        key = (body[self.pk_field], body["id"])
        if key in self.items:
            raise ValueError(f"conflict {key}")
        stored = dict(body)
        self.items[key] = stored
        return dict(stored)

    def read_item(self, item: str, partition_key: str) -> dict:
        key = (partition_key, item)
        if key not in self.items:
            raise _not_found()
        return dict(self.items[key])

    def replace_item(self, item: str, body: dict) -> dict:
        key = (body[self.pk_field], item if isinstance(item, str) else item["id"])
        if key not in self.items:
            raise _not_found()
        self.items[key] = dict(body)
        return dict(body)

    def query_items(self, query: str, parameters=None, partition_key=None, **_kwargs):
        rows = [dict(v) for v in self.items.values()]
        if partition_key is not None:
            rows = [r for r in rows if r.get(self.pk_field) == partition_key]
        return rows

    def delete_item(self, item: str, partition_key: str) -> None:
        key = (partition_key, item)
        if key not in self.items:
            raise _not_found()
        del self.items[key]


class FakeDatabase:
    def __init__(self) -> None:
        self._containers = {
            SOURCES_CONTAINER: FakeContainer("id"),
            TENANTS_CONTAINER: FakeContainer("source_id"),
            RUNS_CONTAINER: FakeContainer("source_tenant_id"),
            REQUESTS_CONTAINER: FakeContainer("source_tenant_id"),
            CURSORS_CONTAINER: FakeContainer("source_tenant_id"),
            RAW_CONTAINER: FakeContainer("source_tenant_id"),
            CANONICAL_CONTAINER: FakeContainer("id"),
            LINKS_CONTAINER: FakeContainer("raw_id"),
            RATE_LIMITS_CONTAINER: FakeContainer("source_tenant_id"),
            SCHEDULES_CONTAINER: FakeContainer("source_tenant_id"),
        }
        self.created: list[dict] = []

    def get_container_client(self, name: str) -> FakeContainer:
        return self._containers[name]

    def create_container_if_not_exists(self, **kwargs) -> None:
        self.created.append(kwargs)


@pytest.fixture(params=["memory", "cosmos"])
def store(request):
    if request.param == "memory":
        return InMemoryJobSourceStore()
    cosmos = CosmosJobSourceStore(FakeDatabase())
    cosmos.seed_sources()
    return cosmos


def _posting(**overrides):
    payload = {
        "source_posting_id": "gh-1",
        "title": "Staff Engineer",
        "location": "Remote",
        "employment_type": "full-time",
        "body": "Build the crawler.",
        "payload": '{"id":"gh-1","title":"Staff Engineer"}',
        "listing_state": "open",
        "namespace": "acme",
    }
    payload.update(overrides)
    return payload


def test_container_specs_match_prd():
    specs = {item["id"]: item for item in container_specs()}
    expected = {
        SOURCES_CONTAINER: SOURCES_PK,
        TENANTS_CONTAINER: TENANTS_PK,
        RUNS_CONTAINER: RUNS_PK,
        REQUESTS_CONTAINER: REQUESTS_PK,
        CURSORS_CONTAINER: CURSORS_PK,
        RAW_CONTAINER: RAW_PK,
        CANONICAL_CONTAINER: CANONICAL_PK,
        LINKS_CONTAINER: LINKS_PK,
        RATE_LIMITS_CONTAINER: RATE_LIMITS_PK,
        SCHEDULES_CONTAINER: SCHEDULES_PK,
    }
    assert set(specs) == set(expected)
    for name, pk in expected.items():
        assert specs[name]["partition_key"] == pk
        assert specs[name]["indexing_policy"]["compositeIndexes"]


def test_ensure_job_source_containers_creates_ten():
    database = FakeDatabase()
    ensure_job_source_containers(database)
    assert {item["id"] for item in database.created} == {
        SOURCES_CONTAINER,
        TENANTS_CONTAINER,
        RUNS_CONTAINER,
        REQUESTS_CONTAINER,
        CURSORS_CONTAINER,
        RAW_CONTAINER,
        CANONICAL_CONTAINER,
        LINKS_CONTAINER,
        RATE_LIMITS_CONTAINER,
        SCHEDULES_CONTAINER,
    }


def test_canonical_and_dedupe_hashes_are_stable():
    key = canonical_key(title=" Staff Engineer ", location="Remote", namespace="Acme")
    assert key == "staff-engineer|remote|acme"
    assert dedupe_hash(key=key, body="  Hello  World ", employment_type="Full-Time") == dedupe_hash(
        key=key, body="hello world", employment_type="full-time"
    )
    assert response_hash('{"a":1}') == response_hash('{"a":1}')
    assert response_hash('{"a":1}') != response_hash('{"a":2}')


def test_seeded_greenhouse_and_lever(store):
    sources = {item.id: item for item in store.list_sources()}
    assert set(sources) == {"greenhouse", "lever"}
    assert sources["greenhouse"].type == "greenhouse"
    assert sources["lever"].name == "Lever"


def test_tenant_unique_per_source_and_key(store):
    first = store.upsert_tenant("greenhouse", "acme", config={"board_token": "t1"})
    again = store.upsert_tenant("greenhouse", "acme", config={"board_token": "t2"}, enabled=False)
    assert again.id == first.id
    assert again.config["board_token"] == "t2"
    assert again.enabled is False
    other = store.upsert_tenant("lever", "acme")
    assert other.id != first.id
    assert len(store.list_tenants("greenhouse")) == 1
    with pytest.raises(JobSourceNotFoundError):
        store.upsert_tenant("unknown", "acme")
    with pytest.raises(JobSourceValidationError):
        store.upsert_tenant("greenhouse", "   ")


def test_delete_tenant_drops_board_and_closes_postings(store):
    tenant = store.upsert_tenant("greenhouse", "bad-board", config={"board_token": "bad-board"})
    keep = store.upsert_tenant("greenhouse", "keep-board", config={"board_token": "keep-board"})
    store.ingest_raw(tenant.id, **_posting(source_posting_id="gone", namespace="bad-board", company="Bad"))
    store.ingest_raw(
        keep.id,
        **_posting(source_posting_id="stay", namespace="keep-board", company="Keep", title="Keep Role"),
    )
    deleted = store.delete_tenant(tenant.id)
    assert deleted.id == tenant.id
    assert deleted.tenant_key == "bad-board"
    remaining = store.list_tenants("greenhouse")
    assert [item.tenant_key for item in remaining] == ["keep-board"]
    with pytest.raises(JobSourceNotFoundError):
        store.get_tenant(tenant.id)
    with pytest.raises(JobSourceNotFoundError):
        store.delete_tenant(tenant.id)
    assert store.list_raw(tenant.id, current_only=True) == []
    assert store.list_raw(keep.id, current_only=True)
    store.delete_tenant(keep.id)
    assert store.list_tenants("greenhouse") == []


def test_cursor_unique_per_endpoint_and_reset_logs_run(store):
    tenant = store.upsert_tenant("greenhouse", "acme")
    run = store.start_run(tenant.id)
    first = store.save_cursor(tenant.id, "list", "page-2")
    second = store.save_cursor(tenant.id, "list", "page-3")
    assert first.id == second.id == f"{tenant.id}:list"
    assert store.get_cursor(tenant.id, "list").cursor == "page-3"
    detail = store.save_cursor(tenant.id, "detail", "job-9")
    assert detail.id != second.id
    reset = store.reset_cursor(tenant.id, "list", run_id=run.id)
    assert reset.cursor is None
    logged = store.get_run(run.id)
    assert "cursor reset for list" in (logged.error_summary or "")


def test_unchanged_ingest_is_noop_and_keeps_one_current_row(store):
    tenant = store.upsert_tenant("greenhouse", "acme")
    run = store.start_run(tenant.id)
    raw, outcome = store.ingest_raw(tenant.id, run_id=run.id, **_posting())
    assert outcome == "created"
    assert raw.is_current is True
    again, outcome = store.ingest_raw(tenant.id, run_id=run.id, **_posting())
    assert outcome == "unchanged"
    assert again.id == raw.id
    assert again.seen_last_at >= raw.seen_last_at
    rows = store.list_raw(tenant.id)
    assert len(rows) == 1
    assert store.list_raw(tenant.id, current_only=True) == rows
    counted = store.get_run(run.id)
    assert counted.noop_count == 1
    assert counted.fetched_count == 1
    assert len(store.list_links(raw_id=raw.id)) == 1


def test_content_change_versions_raw_and_keeps_single_current(store):
    tenant = store.upsert_tenant("greenhouse", "acme")
    first, _ = store.ingest_raw(tenant.id, **_posting())
    updated, outcome = store.ingest_raw(
        tenant.id, **_posting(body="New description.", payload='{"id":"gh-1","rev":2}')
    )
    assert outcome == "updated"
    assert updated.id != first.id
    assert updated.seen_first_at == first.seen_first_at
    rows = store.list_raw(tenant.id)
    assert len(rows) == 2
    current = store.list_raw(tenant.id, current_only=True)
    assert len(current) == 1
    assert current[0].id == updated.id
    historic = [item for item in rows if item.id == first.id][0]
    assert historic.is_current is False


def test_closed_posting_deactivates_canonical_when_no_current_links(store):
    tenant = store.upsert_tenant("greenhouse", "acme")
    raw, _ = store.ingest_raw(tenant.id, **_posting())
    canonicals = store.list_canonical()
    assert len(canonicals) == 1
    assert canonicals[0].is_active is True
    closed, outcome = store.ingest_raw(
        tenant.id, **_posting(listing_state="closed", payload='{"id":"gh-1","state":"closed"}')
    )
    assert outcome == "updated"
    assert closed.is_current is False
    assert store.list_raw(tenant.id, current_only=True) == []
    assert store.list_canonical()[0].is_active is False
    again, outcome = store.ingest_raw(
        tenant.id, **_posting(listing_state="closed", payload='{"id":"gh-1","state":"closed"}')
    )
    assert outcome == "unchanged"
    assert again.id == closed.id
    assert len(store.list_raw(tenant.id)) == 2


def test_close_posting_helper_deactivates_canonical(store):
    tenant = store.upsert_tenant("greenhouse", "acme")
    store.ingest_raw(tenant.id, **_posting())
    closed = store.close_posting(tenant.id, "gh-1")
    assert closed.listing_state == "closed"
    assert closed.is_current is False
    assert store.list_canonical()[0].is_active is False
    with pytest.raises(JobSourceNotFoundError):
        store.close_posting(tenant.id, "missing")


def test_cross_source_merge_shares_canonical_and_records_link_reason(store):
    greenhouse = store.upsert_tenant("greenhouse", "acme-board")
    lever = store.upsert_tenant("lever", "acme")
    raw_gh, _ = store.ingest_raw(greenhouse.id, **_posting(source_posting_id="gh-1"))
    raw_lv, _ = store.ingest_raw(
        lever.id,
        **_posting(source_posting_id="lv-99", payload='{"id":"lv-99","title":"Staff Engineer"}'),
    )
    canonicals = store.list_canonical()
    assert len(canonicals) == 1
    links = store.list_links(canonical_id=canonicals[0].id)
    assert {item.raw_id for item in links} == {raw_gh.id, raw_lv.id}
    created = [item for item in links if item.raw_id == raw_gh.id][0]
    merged = [item for item in links if item.raw_id == raw_lv.id][0]
    assert created.reason == "created"
    assert created.confidence == 1.0
    assert merged.reason == "merged"
    assert merged.confidence == 0.9
    store.close_posting(greenhouse.id, "gh-1")
    assert store.list_canonical()[0].is_active is True
    store.close_posting(lever.id, "lv-99")
    assert store.list_canonical()[0].is_active is False


def test_rate_limit_consume_and_backoff(store):
    tenant = store.upsert_tenant("greenhouse", "acme")
    start = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = start.isoformat().replace("+00:00", "Z")
    remaining = store.consume_rate_limit(tenant.id, cost=float(DEFAULT_BURST), now=stamp)
    assert remaining.tokens_remaining == 0
    with pytest.raises(JobSourceRateLimitedError):
        store.consume_rate_limit(tenant.id, cost=1.0, now=stamp)
    later = (start + timedelta(seconds=60)).isoformat().replace("+00:00", "Z")
    refilled = store.consume_rate_limit(tenant.id, cost=1.0, now=later)
    assert refilled.tokens_remaining == float(DEFAULT_BURST) - 1
    until = (start + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    run = store.start_run(tenant.id)
    req = store.record_request(
        tenant.id, run.id, endpoint="list", url="https://boards.greenhouse.io/x"
    )
    backed = store.set_backoff(tenant.id, until=until, request_id=req.id)
    assert backed.backoff_until == until
    assert store.list_requests(run.id)[0].rate_limited is True
    with pytest.raises(JobSourceRateLimitedError):
        store.consume_rate_limit(tenant.id, now=later)


def test_due_schedules_pause_and_finish_run_jitter(store):
    tenant = store.upsert_tenant("greenhouse", "acme")
    now = datetime.now(timezone.utc)
    stamp = now.isoformat().replace("+00:00", "Z")
    due = store.due_schedules(now=stamp)
    assert any(item.source_tenant_id == tenant.id for item in due)
    paused = store.set_schedule_paused(tenant.id, True)
    assert paused.is_paused is True
    assert store.due_schedules(now=stamp) == []
    store.set_schedule_paused(tenant.id, False)
    run = store.start_run(tenant.id)
    finished = store.finish_run(run.id, status="succeeded")
    schedule = store.get_schedule(tenant.id)
    delta = (parse_ts(schedule.next_run_after) - parse_ts(finished.finished_at)).total_seconds()
    assert DEFAULT_CRAWL_INTERVAL_SECONDS <= delta <= DEFAULT_CRAWL_INTERVAL_SECONDS + 30
    assert store.due_schedules(now=finished.finished_at) == []


def test_partial_success_when_errors_and_request_retries(store):
    tenant = store.upsert_tenant("lever", "acme")
    run = store.start_run(tenant.id)
    store.record_request(
        tenant.id,
        run.id,
        endpoint="list",
        url="https://api.lever.co/v0/postings/acme",
        status_code=429,
        retry_count=2,
        backoff_ms=1000,
        rate_limited=True,
        error="too many requests",
    )
    finished = store.finish_run(run.id, status="succeeded", error_summary="rate limited")
    assert finished.status == "partial_success"
    assert finished.error_count == 1
    req = store.list_requests(run.id)[0]
    assert req.retry_count == 2
    assert req.backoff_ms == 1000
    with pytest.raises(JobSourceValidationError):
        store.finish_run(run.id, status="nope")


def test_get_job_source_store_defaults_to_memory(monkeypatch):
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    loaded = get_job_source_store()
    assert isinstance(loaded, InMemoryJobSourceStore)
    config.get_settings.cache_clear()

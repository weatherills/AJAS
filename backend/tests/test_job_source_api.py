"""Job Source Backend PRD — HTTP API, scheduler, Greenhouse/Lever crawl."""

from __future__ import annotations

import json

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import source_ingestion as routes
from app.job_sources.http import FetchResponse
from app.job_sources.memory import InMemoryJobSourceStore
from app.job_sources.queues import InMemoryJobQueue
from app.job_sources.runtime import set_service
from app.job_sources.service import CrawlService
from app.job_sources.blobs import InMemoryBlobStore

USER = "admin-1"


class FakeFetcher:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._exact: dict[str, list[FetchResponse | Exception]] = {}

    def script(self, url: str, *responses: FetchResponse | Exception) -> None:
        self._exact.setdefault(url, []).extend(responses)

    def get(self, url: str, timeout=None) -> FetchResponse:
        self.calls.append(url)
        bucket = self._exact.get(url)
        if not bucket:
            return FetchResponse(404, b"{}", {}, url)
        item = bucket.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _json_resp(payload, status=200, headers=None) -> FetchResponse:
    return FetchResponse(
        status,
        json.dumps(payload).encode(),
        headers or {"Content-Type": "application/json"},
    )


def _gh_job(job_id: int, **overrides) -> dict:
    body = {
        "id": job_id,
        "title": "Staff Engineer",
        "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{job_id}",
        "location": {"name": "Remote"},
        "departments": [{"name": "Engineering"}],
        "content": "<p>Build crawlers. Contact jobs@acme.test</p>",
        "company_name": "Acme",
    }
    body.update(overrides)
    return body


def _lever_job(job_id: str, **overrides) -> dict:
    body = {
        "id": job_id,
        "text": "Staff Engineer",
        "categories": {"location": "Remote", "commitment": "Full-time", "team": "Engineering"},
        "hostedUrl": f"https://jobs.lever.co/acme/{job_id}",
        "applyUrl": f"https://jobs.lever.co/acme/{job_id}/apply",
        "description": "<p>Build crawlers.</p>",
        "descriptionPlain": "Build crawlers.",
        "company": "Acme",
    }
    body.update(overrides)
    return body


@pytest.fixture
def queue():
    return InMemoryJobQueue()


@pytest.fixture
def blobs():
    return InMemoryBlobStore()


@pytest.fixture
def fetcher():
    return FakeFetcher()


@pytest.fixture
def store():
    return InMemoryJobSourceStore()


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def svc(monkeypatch, store, queue, blobs, fetcher, sleeps):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = CrawlService(
        store=store,
        queue=queue,
        blobs=blobs,
        fetcher=fetcher,
        sleeper=sleeps.append,
    )
    set_service(service)
    yield service
    set_service(None)
    get_settings.cache_clear()


def _req(method: str, url: str, *, user: str | None = USER, route=None) -> func.HttpRequest:
    headers = {}
    if user:
        headers["Authorization"] = f"Bearer {user}"
    return func.HttpRequest(
        method=method,
        url=url,
        headers=headers,
        params={},
        route_params=route or {},
        body=b"",
    )


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    return json.loads(raw) if raw else None


def test_function_app_registers_job_source_routes(function_names):
    assert "start_crawl" in function_names
    assert "get_crawl_run" in function_names
    assert "crawl_scheduler" in function_names
    assert "crawl_run_job" in function_names
    assert "job_fetch_job" in function_names
    assert "health" in function_names


def test_unauthenticated_is_401(svc):
    resp = routes.start_crawl(
        _req("POST", "http://localhost/api/v1/sources/x/crawl", user=None, route={"id": "x"})
    )
    assert resp.status_code == 401


def test_unknown_tenant_is_404(svc):
    resp = routes.start_crawl(
        _req("POST", "http://localhost/api/v1/sources/missing/crawl", route={"id": "missing"})
    )
    assert resp.status_code == 404


def test_greenhouse_paginated_crawl_ingests_and_stores_blob(svc, store, fetcher, blobs):
    tenant = store.upsert_tenant("greenhouse", "acme", config={"namespace": "acme"})
    list1 = f"https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    list2 = f"{list1}?page=2"
    fetcher.script(list1, _json_resp({"jobs": [_gh_job(1)], "meta": {"page": 1}}))
    fetcher.script(list2, _json_resp({"jobs": [_gh_job(2, title="Platform Engineer")], "meta": {"page": 2}}))
    fetcher.script(
        f"{list1}?page=3",
        _json_resp({"jobs": []}),
    )
    fetcher.script(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs/1",
        _json_resp(_gh_job(1)),
    )
    fetcher.script(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs/2",
        _json_resp(_gh_job(2, title="Platform Engineer")),
    )
    resp = routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
    )
    assert resp.status_code == 202
    run_id = _body(resp)["runId"]
    svc.drain()
    status = routes.get_crawl_run(
        _req(
            "GET",
            f"http://localhost/api/v1/sources/{tenant.id}/runs/{run_id}",
            route={"id": tenant.id, "run_id": run_id},
        )
    )
    body = _body(status)
    assert status.status_code == 200
    assert body["status"] in {"succeeded", "partial"}
    assert body["fetchedCount"] == 2
    raw = store.list_raw(tenant.id, current_only=True)
    assert {item.source_posting_id for item in raw} == {"1", "2"}
    assert any("jobs@acme.test" not in (item.body or "") for item in raw)
    assert any("[redacted]" in item.body for item in raw)
    assert any(path.endswith("/1.json") for path in blobs.objects)


def test_unchanged_content_is_noop(svc, store, fetcher):
    tenant = store.upsert_tenant("greenhouse", "acme")
    list_url = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    detail = "https://boards-api.greenhouse.io/v1/boards/acme/jobs/1"
    job = _gh_job(1)
    for _ in range(2):
        fetcher.script(list_url, _json_resp({"jobs": [job]}))
        fetcher.script(detail, _json_resp(job))
        routes.start_crawl(
            _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
        )
        svc.drain()
    runs = store.list_runs(tenant.id)
    assert runs[-1].noop_count == 1
    assert len(store.list_raw(tenant.id)) == 1


def test_lever_list_and_detail(svc, store, fetcher):
    tenant = store.upsert_tenant("lever", "acme", config={"company": "Acme"})
    list_url = "https://api.lever.co/v0/postings/acme?mode=json&skip=0&limit=100"
    detail = "https://api.lever.co/v0/postings/acme/lv-1"
    fetcher.script(list_url, _json_resp([_lever_job("lv-1")]))
    fetcher.script(detail, _json_resp(_lever_job("lv-1")))
    resp = routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
    )
    svc.drain()
    run = store.get_run(_body(resp)["runId"])
    assert run.status in {"succeeded", "partial_success"}
    assert store.list_raw(tenant.id, current_only=True)[0].source_posting_id == "lv-1"


def test_ssrf_base_url_is_rejected(svc, store, fetcher):
    tenant = store.upsert_tenant(
        "greenhouse",
        "acme",
        config={"base_url": "http://169.254.169.254/latest/meta-data"},
    )
    resp = routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
    )
    svc.drain()
    run = store.get_run(_body(resp)["runId"])
    assert run.status == "failed"
    assert fetcher.calls == []


def test_retry_after_on_429(svc, store, fetcher, sleeps):
    tenant = store.upsert_tenant("greenhouse", "acme")
    list_url = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    fetcher.script(
        list_url,
        _json_resp({"error": "slow down"}, status=429, headers={"Retry-After": "2"}),
        _json_resp({"jobs": []}),
    )
    routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
    )
    svc.drain()
    assert 2.0 in sleeps
    run = store.list_runs(tenant.id)[-1]
    assert run.status in {"succeeded", "partial_success"}


def test_missing_title_is_skipped(svc, store, fetcher):
    tenant = store.upsert_tenant("greenhouse", "acme")
    list_url = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    detail = "https://boards-api.greenhouse.io/v1/boards/acme/jobs/9"
    fetcher.script(list_url, _json_resp({"jobs": [_gh_job(9)]}))
    fetcher.script(detail, _json_resp(_gh_job(9, title="", absolute_url="")))
    routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
    )
    svc.drain()
    assert store.list_raw(tenant.id) == []
    run = store.list_runs(tenant.id)[-1]
    assert run.error_count >= 1
    assert run.status == "partial_success"


def test_invalid_cursor_resets_and_logs(svc, store, fetcher):
    tenant = store.upsert_tenant("greenhouse", "acme")
    store.save_cursor(tenant.id, "list", "99")
    stale = "https://boards-api.greenhouse.io/v1/boards/acme/jobs?page=99"
    fresh = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    fetcher.script(stale, FetchResponse(404, b"{}", {}, stale))
    fetcher.script(fresh, _json_resp({"jobs": []}))
    routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
    )
    svc.drain()
    cursor = store.get_cursor(tenant.id, "list")
    assert cursor is None or cursor.cursor is None
    run = store.list_runs(tenant.id)[-1]
    assert run.error_summary and "cursor reset" in run.error_summary


def test_duplicate_page_token_stops(svc, store, fetcher):
    tenant = store.upsert_tenant("greenhouse", "acme")
    list1 = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    list2 = f"{list1}?page=2"
    fetcher.script(list1, _json_resp({"jobs": [_gh_job(1)], "meta": {"page": 1}}))
    fetcher.script(list2, _json_resp({"jobs": [_gh_job(1)], "meta": {"page": 1}}))
    fetcher.script(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs/1",
        _json_resp(_gh_job(1)),
    )
    routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
    )
    svc.drain()
    listing = [url for url in fetcher.calls if url.rstrip("/").endswith("jobs") or "jobs?page=" in url]
    assert listing.count(list2) == 1
    assert len(store.list_raw(tenant.id, current_only=True)) == 1


def test_two_consecutive_misses_deactivate(svc, store, fetcher):
    tenant = store.upsert_tenant("greenhouse", "acme")
    list_url = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    d1 = "https://boards-api.greenhouse.io/v1/boards/acme/jobs/1"
    d2 = "https://boards-api.greenhouse.io/v1/boards/acme/jobs/2"

    def crawl(jobs: list[int]) -> None:
        fetcher.script(list_url, _json_resp({"jobs": [_gh_job(i) for i in jobs]}))
        for job_id in jobs:
            fetcher.script(
                f"https://boards-api.greenhouse.io/v1/boards/acme/jobs/{job_id}",
                _json_resp(_gh_job(job_id)),
            )
        routes.start_crawl(
            _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
        )
        svc.drain()

    crawl([1, 2])
    assert {item.source_posting_id for item in store.list_raw(tenant.id, current_only=True)} == {"1", "2"}
    crawl([1])
    assert {item.source_posting_id for item in store.list_raw(tenant.id, current_only=True)} == {"1", "2"}
    crawl([1])
    current = {item.source_posting_id for item in store.list_raw(tenant.id, current_only=True)}
    assert current == {"1"}
    assert store.list_canonical()[0].is_active is True


def test_scheduler_skips_paused_and_disabled(svc, store, queue):
    due = store.upsert_tenant("greenhouse", "due-board")
    paused = store.upsert_tenant("lever", "paused-board")
    disabled = store.upsert_tenant("greenhouse", "off-board", enabled=False)
    store.set_schedule_paused(paused.id, True)
    queued = svc.schedule_due()
    ids = {item["tenantId"] for item in queued}
    assert due.id in ids
    assert paused.id not in ids
    assert disabled.id not in ids
    assert queue.of("crawl-runs")


def test_poison_message_fails_run(svc, store):
    tenant = store.upsert_tenant("greenhouse", "acme")
    run = store.start_run(tenant.id, status="queued")
    finished = svc.process_crawl_run({"tenantId": tenant.id, "runId": run.id}, dequeue_count=11)
    assert finished.status == "failed"
    assert "poisoned" in (finished.error_summary or "")


def test_department_filter(svc, store, fetcher):
    tenant = store.upsert_tenant(
        "greenhouse",
        "acme",
        config={"filters": {"department": "Sales"}},
    )
    list_url = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    fetcher.script(list_url, _json_resp({"jobs": [_gh_job(1), _gh_job(2, departments=[{"name": "Sales"}])]}))
    fetcher.script(
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs/2",
        _json_resp(_gh_job(2, departments=[{"name": "Sales"}])),
    )
    routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
    )
    svc.drain()
    raw = store.list_raw(tenant.id, current_only=True)
    assert [item.source_posting_id for item in raw] == ["2"]


def test_disabled_tenant_rejected(svc, store):
    tenant = store.upsert_tenant("greenhouse", "acme", enabled=False)
    resp = routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{tenant.id}/crawl", route={"id": tenant.id})
    )
    assert resp.status_code == 400


def test_run_from_other_tenant_is_404(svc, store, fetcher):
    one = store.upsert_tenant("greenhouse", "one")
    two = store.upsert_tenant("lever", "two")
    list_url = "https://boards-api.greenhouse.io/v1/boards/one/jobs"
    fetcher.script(list_url, _json_resp({"jobs": []}))
    resp = routes.start_crawl(
        _req("POST", f"http://localhost/api/v1/sources/{one.id}/crawl", route={"id": one.id})
    )
    svc.drain()
    run_id = _body(resp)["runId"]
    other = routes.get_crawl_run(
        _req(
            "GET",
            f"http://localhost/api/v1/sources/{two.id}/runs/{run_id}",
            route={"id": two.id, "run_id": run_id},
        )
    )
    assert other.status_code == 404

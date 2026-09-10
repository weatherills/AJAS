"""Cross-feature wiring: Matching → Review, Settings → Matching prefs."""

from __future__ import annotations

import json

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import matching as matching_routes
from app.features import settings as settings_routes
from app.job_sources.memory import InMemoryJobSourceStore
from app.job_sources.queues import InMemoryJobQueue as JobsQueue
from app.job_sources.runtime import set_service as set_jobs
from app.job_sources.service import CrawlService
from app.matching.memory import InMemoryMatchingStore
from app.matching.queues import InMemoryJobQueue as MatchingQueue
from app.matching.runtime import set_service as set_matching
from app.matching.service import MatchingService
from app.review.blobs import InMemoryBlobStore
from app.review.memory import InMemoryReviewStore
from app.review.queues import InMemoryJobQueue as ReviewQueue
from app.review.runtime import set_service as set_review
from app.review.service import ReviewService
from app.settings.memory import InMemorySettingsStore
from app.settings.queues import InMemoryJobQueue as SettingsQueue
from app.settings.runtime import set_service as set_settings
from app.settings.service import SettingsService

USER = "user-1"
RESUME = "python azure cosmos functions kubernetes terraform"
HIGH_JOB = "Title: python azure cosmos functions kubernetes terraform\nSkills: python azure cosmos"


def _req(method: str, url: str, *, json_body=None, user: str = USER) -> func.HttpRequest:
    hdrs = {"Authorization": f"Bearer {user}"}
    raw = b""
    if json_body is not None:
        hdrs["Content-Type"] = "application/json"
        raw = json.dumps(json_body).encode()
    return func.HttpRequest(method=method, url=url, headers=hdrs, params={}, route_params={}, body=raw)


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    return json.loads(raw) if raw else None


@pytest.fixture
def wiring(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    get_settings.cache_clear()
    review_store = InMemoryReviewStore()
    matching_store = InMemoryMatchingStore()
    set_review(ReviewService(store=review_store, queue=ReviewQueue(), blobs=InMemoryBlobStore()))
    set_matching(MatchingService(store=matching_store, queue=MatchingQueue()))
    set_settings(SettingsService(store=InMemorySettingsStore(), queue=SettingsQueue()))
    jobs = CrawlService(store=InMemoryJobSourceStore(), queue=JobsQueue())
    jobs.store.upsert_tenant("greenhouse", "acme", config={})
    jobs.store.upsert_tenant("lever", "acme", config={})
    set_jobs(jobs)
    yield {"review": review_store, "matching": matching_store, "jobs": jobs}
    set_review(None)
    set_matching(None)
    set_settings(None)
    set_jobs(None)
    get_settings.cache_clear()


def test_persisted_score_creates_review_row(wiring):
    resp = matching_routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={
                "resumeId": "resume-1",
                "resumeText": RESUME,
                "jobId": "job-high",
                "jobText": HIGH_JOB,
            },
        )
    )
    assert resp.status_code == 200
    body = _body(resp)
    assert body["persisted"] is True
    rows = wiring["review"].list_matches(USER)
    assert len(rows) == 1
    assert rows[0].job_id == "job-high"
    assert rows[0].resume_id == "resume-1"
    assert rows[0].status == "PENDING"
    again = matching_routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={
                "resumeId": "resume-1",
                "resumeText": RESUME,
                "jobId": "job-high",
                "jobText": HIGH_JOB,
            },
        )
    )
    assert again.status_code == 200
    assert len(wiring["review"].list_matches(USER)) == 1


def test_settings_threshold_updates_matching_prefs(wiring):
    resp = settings_routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": 0.85})
    )
    assert resp.status_code == 200
    prefs = wiring["matching"].get_or_create_prefs(USER)
    assert prefs.threshold_pct == 85


def test_settings_source_toggle_disables_tenants(wiring):
    resp = settings_routes.patch_settings(
        _req(
            "PATCH",
            "http://localhost/api/v1/settings",
            json_body={"sources": {"greenhouseEnabled": False, "leverEnabled": True}},
        )
    )
    assert resp.status_code == 200
    gh = wiring["jobs"].store.list_tenants("greenhouse")
    lv = wiring["jobs"].store.list_tenants("lever")
    assert gh and all(not item.enabled for item in gh)
    assert lv and all(item.enabled for item in lv)


def test_demo_review_seed_uses_feed_job_ids(monkeypatch):
    from app.job_sources.feed import feed_cards, seed_demo_feed
    from app.job_sources.memory import InMemoryJobSourceStore
    from app.review.memory import InMemoryReviewStore
    from app.review import runtime

    jobs = InMemoryJobSourceStore()
    seed_demo_feed(jobs)
    cards = feed_cards(jobs)
    monkeypatch.setattr(runtime, "_feed_cards", lambda: cards)
    review = InMemoryReviewStore()
    runtime._seed_demo_matches(review)
    ids = {card["id"] for card in cards}
    matches = review.list_matches("local-user")
    assert matches
    staff = next(item for item in matches if "staff" in item.job_title.lower())
    analyst = next(item for item in matches if "analyst" in item.job_title.lower())
    assert staff.job_id in ids
    assert analyst.job_id in ids
    assert staff.company == "Acme"

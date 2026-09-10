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
    review_svc = ReviewService(store=review_store, queue=ReviewQueue(), blobs=InMemoryBlobStore())
    set_review(review_svc)
    set_matching(MatchingService(store=matching_store, queue=MatchingQueue()))
    set_settings(SettingsService(store=InMemorySettingsStore(), queue=SettingsQueue()))
    jobs = CrawlService(store=InMemoryJobSourceStore(), queue=JobsQueue())
    jobs.store.upsert_tenant("greenhouse", "acme", config={})
    jobs.store.upsert_tenant("lever", "acme", config={})
    set_jobs(jobs)
    yield {"review": review_store, "matching": matching_store, "jobs": jobs, "review_svc": review_svc}
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
    assert wiring["review"].list_matches(USER)[0].source == "ai"


def test_save_match_below_threshold_lands_on_review_saved(wiring):
    low_job = "Title: Baker\nCompany: Cakes\nSkills: frosting pastry whisk\nBake cakes daily with fondant"
    resp = matching_routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={
                "resumeId": "resume-1",
                "resumeText": RESUME,
                "jobId": "job-baker",
                "jobText": low_job,
                "persist": True,
            },
        )
    )
    assert resp.status_code == 200
    body = _body(resp)
    assert body["persisted"] is True
    assert body["score"] < 70
    rows = wiring["review"].list_matches(USER)
    assert len(rows) == 1
    assert rows[0].job_id == "job-baker"
    assert rows[0].source == "saved"
    assert rows[0].status == "PENDING"
    assert rows[0].ai_score == body["score"]
    again = matching_routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={
                "resumeId": "resume-1",
                "resumeText": RESUME,
                "jobId": "job-baker",
                "jobText": low_job,
                "persist": True,
            },
        )
    )
    assert again.status_code == 200
    updated = wiring["review"].list_matches(USER)
    assert len(updated) == 1
    assert updated[0].source == "saved"
    assert updated[0].ai_score == _body(again)["score"]


def test_save_match_replaces_seeded_ai_row_for_same_job(wiring):
    review = wiring["review"]
    seeded = review.create_match(
        USER,
        job_id="job-staff",
        resume_id="resume-1",
        job_title="Staff Engineer",
        company="Acme",
        location="Remote",
        ai_score=88.0,
        suggestion="approve",
        source="ai",
        why="Seeded demo overlap.",
        summary="Seeded demo overlap.",
    )
    low_job = (
        "Title: Staff Engineer\nCompany: Acme\nSkills: frosting pastry whisk\n"
        "Bake cakes daily with fondant. Staff Engineer Acme posting."
    )
    resp = matching_routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={
                "resumeId": "resume-1",
                "resumeText": RESUME,
                "jobId": "job-staff",
                "jobText": low_job,
                "persist": True,
            },
        )
    )
    assert resp.status_code == 200
    body = _body(resp)
    assert body["persisted"] is True
    rows = review.list_matches(USER)
    assert len(rows) == 1
    assert rows[0].id == seeded.id
    assert rows[0].source == "saved"
    assert rows[0].ai_score == body["score"]
    listed = wiring["review_svc"].list_matches(USER, source="ai")
    assert listed["items"] == []
    saved = wiring["review_svc"].list_matches(USER, source="saved")
    assert len(saved["items"]) == 1
    assert saved["items"][0]["matchId"] == seeded.id
    assert saved["items"][0]["score"] == body["score"]


def test_list_hides_ai_seed_when_saved_duplicate_exists(wiring):
    review = wiring["review"]
    review.create_match(
        USER,
        job_id="job-staff",
        resume_id="resume-1",
        job_title="Staff Engineer",
        company="Acme",
        location="Remote",
        ai_score=88.0,
        source="ai",
    )
    saved = review.create_match(
        USER,
        job_id="job-staff",
        resume_id="resume-1",
        job_title="Staff Engineer",
        company="Acme",
        location="Remote",
        ai_score=48.1,
        source="saved",
    )
    svc = wiring["review_svc"]
    matches = svc.list_matches(USER, source="ai", status="awaiting")
    assert matches["items"] == []
    saved_list = svc.list_matches(USER, source="saved", status="awaiting")
    assert [item["matchId"] for item in saved_list["items"]] == [saved.id]
    assert saved_list["items"][0]["score"] == 48.1


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


def test_demo_resume_seed_matches_review_id():
    from app.resumes.demo import DEMO_RESUME_ID, DEMO_USER, seed_demo_resume
    from app.resumes.memory import InMemoryResumeStore

    store = InMemoryResumeStore()
    seed_demo_resume(store)
    row = store.get_resume(DEMO_USER, DEMO_RESUME_ID)
    assert row.id == "resume-1"
    assert row.validated is True
    assert row.processing_status == "parsed"
    seed_demo_resume(store)
    assert len(store.list_resumes(DEMO_USER)) == 1


def test_demo_review_seed_resume_id_is_resume_1(monkeypatch):
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
    matches = review.list_matches("local-user")
    assert matches
    assert {item.resume_id for item in matches} == {"resume-1"}


def test_learning_demo_jobs_align_with_feed(monkeypatch):
    from app.job_sources.feed import feed_cards, seed_demo_feed
    from app.job_sources.memory import InMemoryJobSourceStore
    from app.learning.memory import InMemoryLearningStore

    jobs = InMemoryJobSourceStore()
    seed_demo_feed(jobs)
    ids = {card["id"] for card in feed_cards(jobs)}
    monkeypatch.setattr("app.job_sources.store.get_job_source_store", lambda: jobs)
    store = InMemoryLearningStore(seed=False)
    store.seed_demo("local-user", align_feed=True)
    named = [row.job_id for row in store.list_recommendations("local-user") if not row.job_id.startswith("job-extra-")]
    assert named
    assert any(job_id in ids for job_id in named)
    assert all(row.resume_id == "resume-1" for row in store.list_recommendations("local-user"))

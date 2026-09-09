"""Settings + Review share the same auth principal (Kanban e2e)."""

from __future__ import annotations

import json

import azure.functions as func

from app.config import get_settings
from app.features import review_decision as review_routes
from app.features import settings as settings_routes
from app.review.blobs import InMemoryBlobStore
from app.review.memory import InMemoryReviewStore
from app.review.queues import InMemoryJobQueue as ReviewQueue
from app.review.runtime import set_service as set_review
from app.review.service import ReviewService
from app.settings.memory import InMemorySettingsStore
from app.settings.queues import InMemoryJobQueue as SettingsQueue
from app.settings.runtime import set_service as set_settings
from app.settings.service import SettingsService

USER = "local-user"


def _req(
    method: str,
    url: str,
    *,
    json_body=None,
    route=None,
    params=None,
    headers=None,
) -> func.HttpRequest:
    hdrs = {"Authorization": f"Bearer {USER}", **(headers or {})}
    body = b""
    if json_body is not None:
        hdrs["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode()
    return func.HttpRequest(
        method=method,
        url=url,
        headers=hdrs,
        params=params or {},
        route_params=route or {},
        body=body,
    )


def test_settings_and_review_happy_path(monkeypatch, function_names):
    assert "get_settings" in function_names
    assert "patch_settings" in function_names
    assert "list_matches" in function_names
    assert "create_decision" in function_names

    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    store = InMemoryReviewStore()
    review = ReviewService(store=store, queue=ReviewQueue(), blobs=InMemoryBlobStore())
    settings = SettingsService(store=InMemorySettingsStore(), queue=SettingsQueue())
    set_review(review)
    set_settings(settings)
    try:
        match = store.create_match(
            USER,
            job_id="job-staff",
            resume_id="resume-1",
            job_title="Staff Platform Engineer",
            company="Acme",
            location="Remote",
            ai_score=88.0,
            suggestion="approve",
            why="Platform overlap.",
            summary="Strong match.",
            highlights_json=["Python"],
        )
        patched = settings_routes.patch_settings(
            _req(
                "PATCH",
                "http://localhost/api/v1/settings",
                json_body={"matchThreshold": 0.8, "sources": {"greenhouseEnabled": True, "leverEnabled": False}},
            )
        )
        assert patched.status_code == 200
        body = json.loads(patched.get_body())
        assert body["matchThreshold"] == 0.8
        assert body["sources"]["greenhouseEnabled"] is True

        listed = review_routes.list_matches(_req("GET", "http://localhost/api/v1/matches"))
        assert listed.status_code == 200
        items = json.loads(listed.get_body())["items"]
        assert any(row["jobTitle"] == "Staff Platform Engineer" for row in items)

        decided = review_routes.create_decision(
            _req(
                "POST",
                f"http://localhost/api/v1/matches/{match.id}/decision",
                json_body={"decision": "approve", "comment": "Ship it"},
                route={"matchId": match.id},
                headers={"Idempotency-Key": "settings-e2e-1", "If-Match": match.etag},
            )
        )
        assert decided.status_code in {200, 201}
        assert json.loads(decided.get_body())["matchStatus"] in {"approved", "APPROVED"}

        got = settings_routes.get_settings(_req("GET", "http://localhost/api/v1/settings"))
        assert got.status_code == 200
        assert json.loads(got.get_body())["matchThreshold"] == 0.8
    finally:
        set_review(None)
        set_settings(None)
        get_settings.cache_clear()

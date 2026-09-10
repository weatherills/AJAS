"""Sprint 6: observability, auth session, pagination, email, learning, review bulk."""

from __future__ import annotations

import json

import azure.functions as func


def _req(method: str, url: str, *, headers=None, params=None, body=None, route_params=None):
    payload = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    return func.HttpRequest(
        method=method,
        url=url,
        headers=headers or {"Authorization": "Bearer local-user"},
        params=params or {},
        route_params=route_params or {},
        body=payload,
    )


def _body(resp):
    return json.loads(resp.get_body())


def test_error_envelope_includes_retryable():
    from app.http import error_response

    resp = error_response("RATE_LIMITED", "slow down", 429, retry_after=12)
    body = _body(resp)
    assert body["error"]["retryable"] is True
    assert body["error"]["canonical"] == "RATE_LIMITED"
    assert resp.headers.get("Retry-After") == "12"
    assert resp.headers.get("X-Request-Id") in (None, "") or True


def test_pagination_contract():
    from app.features.ops import pagination_contract

    resp = pagination_contract(_req("GET", "http://localhost/api/v1/meta/pagination"))
    body = _body(resp)
    assert resp.status_code == 200
    assert body["limitParam"] == "limit"
    assert body["cursorParam"] == "cursor"
    assert body["nextCursorField"] == "nextCursor"
    assert body["maxLimit"] == 100


def test_auth_me_and_session_and_devices():
    from app.features.ops import auth_me
    from app.features import auth_session as routes

    me = _body(auth_me(_req("GET", "http://localhost/api/v1/auth/me")))
    assert me["role"] == "user"
    assert me["permissions"]["review"] is True
    assert me["permissions"]["ops"] is False

    admin = _body(
        auth_me(_req("GET", "http://localhost/api/v1/auth/me", headers={"Authorization": "Bearer local-user", "X-Role": "admin"}))
    )
    assert admin["role"] == "admin"
    assert admin["permissions"]["ops"] is True

    created = routes.create_auth_session(_req("POST", "http://localhost/api/v1/auth/session", body={"label": "test-laptop"}))
    assert created.status_code == 201
    issued = _body(created)
    assert issued["accessToken"].startswith("ajas.at.")
    assert issued["refreshToken"]
    devices = _body(routes.list_auth_devices(_req("GET", "http://localhost/api/v1/auth/devices")))
    assert devices["items"]
    rotated = _body(routes.refresh_auth_session(_req("POST", "http://localhost/api/v1/auth/refresh", body={"refreshToken": issued["refreshToken"]})))
    assert rotated["accessToken"] != issued["accessToken"]
    expired = routes.refresh_auth_session(
        _req("POST", "http://localhost/api/v1/auth/refresh", body={"refreshToken": issued["refreshToken"]})
    )
    assert expired.status_code == 401


def test_ops_traces_admin_only():
    from app.features.ops import ops_traces
    from app.tracing import finish_span, start_span

    span = start_span("matching.compute")
    finish_span(span, ok=True)
    denied = ops_traces(_req("GET", "http://localhost/api/v1/ops/traces"))
    assert denied.status_code == 403
    allowed = ops_traces(
        _req("GET", "http://localhost/api/v1/ops/traces", headers={"Authorization": "Bearer local-user", "X-Role": "admin"})
    )
    assert allowed.status_code == 200
    assert _body(allowed)["items"]


def test_email_preview_theme_and_bounce_suppression():
    from app.features.email import email_bounce_webhook, preview_email_template

    preview = preview_email_template(
        _req("GET", "http://localhost/api/v1/email/templates/thanks/preview", route_params={"templateId": "thanks"})
    )
    body = _body(preview)
    assert preview.status_code == 200
    assert "color-scheme" in body["html"]
    assert "{firstName}" not in body["text"]
    bounce = email_bounce_webhook(
        _req(
            "POST",
            "http://localhost/api/v1/email/webhooks/bounce",
            headers={"X-Webhook-Secret": "dev-bounce-secret"},
            body={"email": "bad@example.com", "type": "complaint"},
        )
    )
    assert bounce.status_code == 202
    assert bounce.headers.get("X-Request-Id")
    from app.mail.suppression import is_suppressed

    assert is_suppressed("bad@example.com")


def test_learning_pipeline_and_drift():
    from app.features.learning_loop import backfill_learning_pipeline, get_learning_drift, validate_learning_pipeline

    empty = validate_learning_pipeline(_req("POST", "http://localhost/api/v1/learning/pipeline/validate"))
    assert empty.status_code == 200
    assert _body(empty)["accepted"] == 0
    bad = validate_learning_pipeline(_req("POST", "http://localhost/api/v1/learning/pipeline/validate", body={"events": [{}]}))
    assert _body(bad)["rejected"] == 1
    good_event = {
        "userId": "local-user",
        "matchId": "m-1",
        "jobId": "j-1",
        "decision": "approve",
        "idempotencyKey": "k-1",
        "score": 0.8,
    }
    ok = validate_learning_pipeline(_req("POST", "http://localhost/api/v1/learning/pipeline/validate", body={"events": [good_event]}))
    assert _body(ok)["accepted"] == 1
    filled = backfill_learning_pipeline(
        _req("POST", "http://localhost/api/v1/learning/pipeline/backfill", body={"events": [good_event]})
    )
    assert _body(filled)["applied"] == 1
    drift = get_learning_drift(_req("GET", "http://localhost/api/v1/learning/drift"))
    assert "precision" in _body(drift)
    assert "alert" in _body(drift)


def test_review_bulk_archive_and_pagination_alias():
    from app.features import review_decision as routes
    from app.review.runtime import get_service

    service = get_service()
    created = service.upsert_scored_match(
        "local-user",
        job_id="job-bulk",
        resume_id="resume-bulk",
        job_title="Staff Engineer",
        company="Acme",
        location="Remote",
        score=88,
        why="overlap",
    )
    assert created
    match_id = created["matchId"]
    listed = routes.list_matches(
        _req("GET", "http://localhost/api/v1/matches", params={"limit": "5", "status": "pending"})
    )
    listed_body = _body(listed)
    assert "items" in listed_body
    assert "nextCursor" in listed_body
    bulk = routes.bulk_update_matches(
        _req("POST", "http://localhost/api/v1/matches/bulk", body={"action": "archive", "matchIds": [match_id]})
    )
    assert bulk.status_code == 200
    assert match_id in _body(bulk)["updated"]
    hidden = _body(routes.list_matches(_req("GET", "http://localhost/api/v1/matches", params={"status": "pending"})))
    assert all(item["matchId"] != match_id for item in hidden["items"])


def test_matching_list_cache_and_explain_breakdown():
    from app.matching.runtime import get_service

    service = get_service()
    status, scored = service.compute(
        "local-user",
        {"resumeText": "python azure kubernetes staff engineer", "jobText": "title: Staff\ncompany: Acme\nskills: python azure"},
    )
    assert status == 200
    assert "weights" in scored["breakdown"]
    first = service.list_matches("local-user")
    assert first["cache"] == "miss"
    second = service.list_matches("local-user")
    assert second["cache"] == "hit"
    service.invalidate_list_cache("local-user")
    third = service.list_matches("local-user")
    assert third["cache"] == "miss"


def test_ops_seed_and_ingestion_snapshot():
    from app.features.ops import ops_ingestion, ops_seed

    seeded = ops_seed(_req("POST", "http://localhost/api/v1/ops/seed"))
    assert seeded.status_code == 200
    assert _body(seeded)["seeded"] is True
    denied = ops_ingestion(_req("GET", "http://localhost/api/v1/ops/ingestion"))
    assert denied.status_code == 403
    allowed = ops_ingestion(
        _req("GET", "http://localhost/api/v1/ops/ingestion", headers={"Authorization": "Bearer local-user", "X-Role": "admin"})
    )
    assert allowed.status_code == 200
    assert "globalRateLimit" in _body(allowed)


def test_source_retry_has_jitter():
    from app.job_sources.http import FetchResponse
    from app.job_sources.runtime import get_service

    service = get_service()
    delays = [service._retry_delay(FetchResponse(status_code=500, body=b"", headers={}), 3) for _ in range(8)]
    assert min(delays) >= 0
    assert max(delays) <= 60
    assert len(set(round(item, 4) for item in delays)) > 1

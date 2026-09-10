"""Sprint 7: CORS, CSRF cookies, bounce auth, isolation, probes, production guards."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import azure.functions as func
import jwt

from app.config import get_settings


FIXTURES = Path(__file__).parent / "fixtures"


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


def test_cors_allowlist_and_preflight(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://ajas.example")
    get_settings.cache_clear()
    from app.features.health import cors_preflight, health, ready

    resp = health(
        _req("GET", "http://localhost/api/health", headers={"Origin": "http://localhost:3000"})
    )
    assert resp.status_code == 200
    assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    assert "X-CSRF-Token" in (resp.headers.get("Access-Control-Expose-Headers") or "")
    preflight = cors_preflight(_req("OPTIONS", "http://localhost/api/v1/matches", headers={"Origin": "https://ajas.example"}))
    assert preflight.status_code == 200
    assert preflight.headers.get("Access-Control-Allow-Origin") == "https://ajas.example"
    ready_resp = ready(_req("GET", "http://localhost/api/ready"))
    assert ready_resp.status_code == 200
    assert _body(ready_resp)["ready"] is True
    get_settings.cache_clear()


def test_bounce_webhook_requires_secret():
    from app.features.email import email_bounce_webhook

    denied = email_bounce_webhook(
        _req(
            "POST",
            "http://localhost/api/v1/email/webhooks/bounce",
            headers={},
            body={"email": "unsigned@example.com", "type": "bounce"},
        )
    )
    assert denied.status_code == 401
    ok = email_bounce_webhook(
        _req(
            "POST",
            "http://localhost/api/v1/email/webhooks/bounce",
            headers={"X-Webhook-Secret": "dev-bounce-secret"},
            body={"email": "signed@example.com", "type": "bounce"},
        )
    )
    assert ok.status_code == 202


def test_pii_redacted_in_request_logs(caplog):
    from app.observability import log_request

    with caplog.at_level("INFO", logger="ajas"):
        log_request(
            feature="email",
            route="v1/email/threads",
            method="GET",
            status=200,
            extra={"note": "contact jane@contoso.com at +1-555-01001"},
            error="ssn 123-45-6789 leaked",
        )
    text = caplog.text
    assert "jane@contoso.com" not in text
    assert "123-45-6789" not in text
    assert "[redacted-email]" in text
    assert "[redacted-ssn]" in text


def test_session_cookie_csrf_and_cross_user_device_revoke():
    from app.features import auth_session as routes

    created = routes.create_auth_session(
        _req("POST", "http://localhost/api/v1/auth/session", body={"label": "laptop"})
    )
    assert created.status_code == 201
    issued = _body(created)
    cookie = created.headers.get("Set-Cookie") or ""
    assert "ajas_sess=" in cookie
    assert "HttpOnly" in cookie
    csrf = issued["csrfToken"]
    assert csrf
    assert created.headers.get("X-CSRF-Token") == csrf

    missing = routes.delete_auth_device(
        _req(
            "DELETE",
            f"http://localhost/api/v1/auth/devices/{issued['deviceId']}",
            headers={"Cookie": cookie.split(";", 1)[0]},
            route_params={"deviceId": issued["deviceId"]},
        )
    )
    assert missing.status_code == 401

    allowed = routes.delete_auth_device(
        _req(
            "DELETE",
            f"http://localhost/api/v1/auth/devices/{issued['deviceId']}",
            headers={"Cookie": cookie.split(";", 1)[0], "X-CSRF-Token": csrf},
            route_params={"deviceId": issued["deviceId"]},
        )
    )
    assert allowed.status_code == 200

    other = routes.create_auth_session(
        _req(
            "POST",
            "http://localhost/api/v1/auth/session",
            headers={"Authorization": "Bearer other-user"},
            body={"label": "phone"},
        )
    )
    other_id = _body(other)["deviceId"]
    stolen = routes.delete_auth_device(
        _req(
            "DELETE",
            f"http://localhost/api/v1/auth/devices/{other_id}",
            route_params={"deviceId": other_id},
        )
    )
    assert stolen.status_code == 404


def test_mail_thread_isolation(monkeypatch):
    from app.features import email as routes
    from app.mail.memory import InMemoryEmailStore
    from app.mail.queues import InMemoryJobQueue
    from app.mail.runtime import set_service
    from app.mail.service import EmailService
    from app.mail.graph import LocalGraphClient
    from app.settings.memory import InMemorySettingsStore

    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = EmailService(
        store=InMemoryEmailStore(seed=False),
        queue=InMemoryJobQueue(),
        graph=LocalGraphClient(),
        local_mode=True,
        settings_store=InMemorySettingsStore(),
    )
    set_service(service)
    try:
        mine = routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads"))
        assert mine.status_code == 200
        items = _body(mine)["items"]
        assert items
        thread_id = items[0]["id"]
        other = routes.list_thread_messages(
            _req(
                "GET",
                f"http://localhost/api/v1/threads/{thread_id}/messages",
                headers={"Authorization": "Bearer other-user"},
                route_params={"threadId": thread_id},
            )
        )
        assert other.status_code in {403, 404}
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_review_approve_does_not_enqueue_auto_apply():
    from app.review.blobs import InMemoryBlobStore
    from app.review.memory import InMemoryReviewStore
    from app.review.queues import InMemoryJobQueue
    from app.review.service import ReviewService

    store = InMemoryReviewStore()
    queue = InMemoryJobQueue()
    service = ReviewService(store=store, queue=queue, blobs=InMemoryBlobStore())
    match = store.create_match(
        "local-user",
        job_id="job-1",
        resume_id="resume-1",
        job_title="Staff Engineer",
        company="Acme",
        location="Remote",
        ai_score=90.0,
        suggestion="approve",
        why="overlap",
        summary="strong",
        highlights_json=["Python"],
    )
    service.decide(
        "local-user",
        match.id,
        {"decision": "approve"},
        idempotency_key="k-approve-1",
        etag=match.etag,
    )
    names = [name for name, _body in queue.messages]
    assert all(not name.startswith("auto-apply-") for name in names)
    assert names


def test_matching_persist_does_not_use_job_source_store():
    from app.matching.service import MatchingService

    source = inspect.getsource(MatchingService._persist)
    assert "get_job_source_store" not in source
    assert "self.store" in source


def test_job_source_store_uses_cosmos_when_configured(monkeypatch):
    import app.job_sources.store as store_mod
    from app.config import get_settings as reload_settings

    class FakeCosmos:
        def __init__(self, database):
            self.database = database

    store_mod._store = None
    monkeypatch.setenv("COSMOS_CONNECTION_STRING", "AccountEndpoint=https://example;AccountKey=abc==;")
    reload_settings.cache_clear()
    monkeypatch.setattr("app.job_sources.cosmos_store.CosmosJobSourceStore", FakeCosmos)
    monkeypatch.setattr("app.storage.cosmos.get_database", lambda: object())
    try:
        loaded = store_mod.get_job_source_store()
        assert isinstance(loaded, FakeCosmos)
    finally:
        store_mod._store = None
        monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
        reload_settings.cache_clear()


def test_graph_delta_token_persists_on_store():
    from app.mail.graph import LocalGraphClient
    from app.mail.memory import InMemoryEmailStore
    from app.mail.queues import InMemoryJobQueue
    from app.mail.service import EmailService
    from app.settings.memory import InMemorySettingsStore

    store = InMemoryEmailStore(seed=False)
    graph = LocalGraphClient()
    service = EmailService(
        store=store,
        queue=InMemoryJobQueue(),
        graph=graph,
        local_mode=True,
        settings_store=InMemorySettingsStore(),
    )
    account = service._mailbox("local-user", create_demo=True)
    assert account is not None
    service.process_ingest({"kind": "poll", "accountId": account.id, "userId": "local-user"})
    cursor = store.get_cursor(account.id)
    assert cursor is not None
    assert cursor.delta_token
    restarted = EmailService(
        store=store,
        queue=InMemoryJobQueue(),
        graph=graph,
        local_mode=True,
        settings_store=InMemorySettingsStore(),
    )
    again = restarted.store.get_cursor(account.id)
    assert again is not None
    assert again.delta_token == cursor.delta_token


def test_learning_drift_persists_blob():
    from app.learning.memory import InMemoryLearningStore
    from app.learning.queues import InMemoryJobQueue
    from app.learning.service import LearningService

    store = InMemoryLearningStore(seed=True)
    service = LearningService(store=store, queue=InMemoryJobQueue(), local_mode=True)
    body = service.drift("local-user", period="7d")
    assert "precision" in body
    assert store._blobs[f"drift/local-user/7d.json"]["period"] == "7d"


def test_ingestion_alert_fires_after_three_failures(monkeypatch):
    import app.ingestion_alerts as alerts

    monkeypatch.delenv("INGESTION_ALERT_WEBHOOK", raising=False)
    alerts._last_alert = None
    events = [{"kind": "error", "message": "boom"}] * 3
    assert alerts.maybe_alert(failure_count=3, events=events) is True
    skips = [{"kind": "skip", "demo_seed": True}] * 4
    assert alerts.maybe_alert(failure_count=4, events=skips) is False


def test_vendor_submit_fixtures():
    from app.auto_apply.models import AutoApplyAttempt
    from app.auto_apply.submitters import greenhouse_endpoint, lever_endpoint, map_vendor_fields, submit_to_vendor

    class Poster:
        def __init__(self, payload):
            self.payload = payload
            self.calls = []

        def post(self, url, body, headers):
            self.calls.append((url, body, headers))
            return 200, self.payload

    for name in ("greenhouse_submit.json", "lever_submit.json"):
        fixture = json.loads((FIXTURES / name).read_text())
        from app.auto_apply.keys import utc_now

        attempt = AutoApplyAttempt(
            user_id="local-user",
            job_id=fixture["jobId"],
            posting_url=fixture["postingUrl"],
            vendor=fixture["vendor"],
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        fields = map_vendor_fields(
            fixture["vendor"],
            profile=fixture["profile"],
            answers={},
            autofill=[],
            mappings=[],
        )
        poster = Poster(fixture["response"])
        outcome = submit_to_vendor(attempt, fields, live=True, api_key="test-key", poster=poster)
        assert outcome.status == "succeeded"
        assert poster.calls
        expected = fixture["expectedEndpoint"]
        if fixture["vendor"] == "greenhouse":
            assert greenhouse_endpoint(fixture["postingUrl"], fixture["jobId"]) == expected
            assert poster.calls[0][0] == expected
        else:
            assert lever_endpoint(fixture["postingUrl"], fixture["jobId"]).startswith(expected)
            assert poster.calls[0][0].startswith(expected)


def test_aad_hs256_jwt(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "aad")
    monkeypatch.setenv("AUTH_JWT_SECRET", "sprint7-secret-sprint7-secret-sprint7")
    monkeypatch.delenv("AUTH_JWT_JWKS_URL", raising=False)
    get_settings.cache_clear()
    from app.auth import get_principal

    token = jwt.encode(
        {"oid": "aad-user-1", "scp": "read:review write:review"},
        "sprint7-secret-sprint7-secret-sprint7",
        algorithm="HS256",
    )
    principal = get_principal(
        _req("GET", "http://localhost/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    )
    assert principal.user_id == "aad-user-1"
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()


def test_key_vault_skipped_when_unset(monkeypatch):
    from app.secrets import hydrate_from_key_vault

    monkeypatch.delenv("KEY_VAULT_URI", raising=False)
    monkeypatch.delenv("AZURE_KEY_VAULT_URI", raising=False)
    hydrate_from_key_vault()


def test_key_vault_hydrates_missing_secret(monkeypatch):
    import os
    import sys
    import types

    from app import secrets as secrets_mod

    class FakeSecret:
        value = "from-vault"

    class FakeClient:
        def __init__(self, vault_url, credential):
            self.vault_url = vault_url

        def get_secret(self, name):
            if name == "azure-openai-api-key":
                return FakeSecret()
            raise KeyError(name)

    ident = types.ModuleType("azure.identity")
    ident.DefaultAzureCredential = lambda **_k: object()
    kv = types.ModuleType("azure.keyvault")
    kvs = types.ModuleType("azure.keyvault.secrets")
    kvs.SecretClient = FakeClient
    monkeypatch.setitem(sys.modules, "azure.identity", ident)
    monkeypatch.setitem(sys.modules, "azure.keyvault", kv)
    monkeypatch.setitem(sys.modules, "azure.keyvault.secrets", kvs)
    if "azure.identity" in sys.modules:
        sys.modules["azure.identity"].DefaultAzureCredential = ident.DefaultAzureCredential  # type: ignore[attr-defined]
    if "azure.keyvault.secrets" in sys.modules:
        sys.modules["azure.keyvault.secrets"].SecretClient = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setenv("KEY_VAULT_URI", "https://ajas.vault.azure.net/")
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    secrets_mod.hydrate_from_key_vault()
    assert os.environ.get("AZURE_OPENAI_API_KEY") == "from-vault"


def test_azure_monitor_export_when_configured(monkeypatch, caplog):
    from app.monitor import export_span

    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=demo")
    with caplog.at_level("INFO", logger="ajas"):
        export_span({"traceId": "t1", "spanId": "s1", "name": "review", "elapsedMs": 12, "ok": True})
    assert "ajas.monitor" in caplog.text


def test_auth_config_endpoint():
    from app.features.ops import auth_config

    resp = auth_config(_req("GET", "http://localhost/api/v1/auth/config", headers={}))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["mode"] in {"dev", "aad"}
    assert "configured" in body


def test_slo_samples_record_review_list():
    from app.features import review_decision as routes
    from app.review.blobs import InMemoryBlobStore
    from app.review.memory import InMemoryReviewStore
    from app.review.queues import InMemoryJobQueue
    from app.review.runtime import set_service
    from app.review.service import ReviewService
    from app.slo import snapshot

    set_service(ReviewService(store=InMemoryReviewStore(), queue=InMemoryJobQueue(), blobs=InMemoryBlobStore()))
    try:
        resp = routes.list_matches(_req("GET", "http://localhost/api/v1/matches"))
        assert resp.status_code == 200
        routes_snap = {row["route"]: row for row in snapshot()["slo"]}
        assert routes_snap["GET /v1/matches"]["samples"] >= 1
        assert routes_snap["GET /v1/review"]["samples"] >= 1
    finally:
        set_service(None)

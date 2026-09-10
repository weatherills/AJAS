"""Settings Backend PRD — HTTP API, auth, OAuth, queues."""

from __future__ import annotations

import json

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import settings as routes
from app.settings.memory import InMemorySettingsStore
from app.settings.oauth import GraphError, TokenSet
from app.settings.queues import InMemoryJobQueue
from app.settings.runtime import set_service
from app.settings.service import SettingsService

USER = "user-1"
OTHER = "user-2"
REFRESH = "refresh-plain-secret"


class FakeExchanger:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[dict] = []

    def exchange(self, *, code: str, redirect_uri: str, code_verifier: str) -> TokenSet:
        self.calls.append({"code": code, "redirect_uri": redirect_uri, "code_verifier": code_verifier})
        if self.fail:
            raise GraphError("Microsoft token exchange failed", status_code=502, code="GRAPH_ERROR")
        return TokenSet(
            access_token="access-token",
            refresh_token=REFRESH,
            expires_in=3600,
            scope="offline_access Mail.Read",
            tenant_id="tenant-1",
            account_id="jane@contoso.com",
        )


@pytest.fixture
def queue():
    return InMemoryJobQueue()


@pytest.fixture
def exchanger():
    return FakeExchanger()


@pytest.fixture
def svc(monkeypatch, queue, exchanger):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client-1")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret-1")
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = SettingsService(store=InMemorySettingsStore(), queue=queue, exchanger=exchanger)
    set_service(service)
    yield service
    set_service(None)
    get_settings.cache_clear()


def _req(
    method: str,
    url: str,
    *,
    user: str | None = USER,
    json_body=None,
    route=None,
) -> func.HttpRequest:
    headers = {}
    body = b""
    if user:
        headers["Authorization"] = f"Bearer {user}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode()
    return func.HttpRequest(method=method, url=url, headers=headers, params={}, route_params=route or {}, body=body)


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    return json.loads(raw) if raw else None


def test_function_app_registers_settings_routes(function_names):
    assert "get_settings" in function_names
    assert "patch_settings" in function_names
    assert "connect_email" in function_names
    assert "email_callback" in function_names
    assert "disconnect_email" in function_names
    assert "settings_match_recalc_job" in function_names
    assert "settings_source_discovery_job" in function_names
    assert "health" in function_names


def test_unauthenticated_is_401(svc, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="ajas")
    resp = routes.get_settings(_req("GET", "http://localhost/api/v1/settings", user=None))
    assert resp.status_code == 401
    assert any("ajas.request" in record.getMessage() for record in caplog.records)


def test_get_logs_successful_request(svc, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="ajas")
    resp = routes.get_settings(_req("GET", "http://localhost/api/v1/settings"))
    assert resp.status_code == 200
    assert any("GET /v1/settings" in record.getMessage() for record in caplog.records)


def test_get_defaults_without_secrets(svc):
    resp = routes.get_settings(_req("GET", "http://localhost/api/v1/settings"))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["matchThreshold"] == 0.7
    assert body["sources"] == {"greenhouseEnabled": False, "leverEnabled": False}
    assert body["emailConnection"]["status"] == "disconnected"
    assert body["oauthConfigured"] is True
    assert "secure" not in body["emailConnection"]
    assert "refreshTokenEnc" not in json.dumps(body)
    assert body["audit"]["updatedBy"]


def test_other_user_cannot_read_foreign_settings(svc):
    routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": 0.9})
    )
    other = _body(routes.get_settings(_req("GET", "http://localhost/api/v1/settings", user=OTHER)))
    assert other["matchThreshold"] == 0.7


def test_patch_threshold_enqueues_recalc(svc, queue):
    resp = routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": 0.85})
    )
    assert resp.status_code == 200
    body = _body(resp)
    assert body["matchThreshold"] == 0.85
    assert len(queue.of("match-recalc")) == 1
    msg = queue.of("match-recalc")[0]
    assert msg["userId"] == USER
    assert msg["oldThreshold"] == 0.7
    assert msg["newThreshold"] == 0.85
    again = routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": 0.85})
    )
    assert again.status_code == 200
    assert len(queue.of("match-recalc")) == 1


def test_patch_rejects_out_of_range_threshold(svc):
    resp = routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": 1.2})
    )
    assert resp.status_code == 400
    low = routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": 0.09})
    )
    assert low.status_code == 400
    bad = routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": "hot"})
    )
    assert bad.status_code == 400
    flag = routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": True})
    )
    assert flag.status_code == 400


def test_source_toggle_enqueues_discovery_and_is_idempotent(svc, queue):
    on = routes.patch_settings(
        _req(
            "PATCH",
            "http://localhost/api/v1/settings",
            json_body={"sources": {"greenhouseEnabled": True}},
        )
    )
    assert on.status_code == 200
    assert _body(on)["sources"]["greenhouseEnabled"] is True
    assert queue.of("source-discovery") == [{"userId": USER, "source": "greenhouse"}]
    again = routes.patch_settings(
        _req(
            "PATCH",
            "http://localhost/api/v1/settings",
            json_body={"sources": {"greenhouseEnabled": True}},
        )
    )
    assert again.status_code == 200
    assert queue.of("source-discovery") == [{"userId": USER, "source": "greenhouse"}]
    off = routes.patch_settings(
        _req(
            "PATCH",
            "http://localhost/api/v1/settings",
            json_body={"sources": {"greenhouseEnabled": False}},
        )
    )
    assert _body(off)["sources"]["greenhouseEnabled"] is False
    assert queue.of("source-discovery") == [{"userId": USER, "source": "greenhouse"}]


def test_get_reports_sources_unconfigured_when_no_tenants(svc):
    from app.job_sources.memory import InMemoryJobSourceStore
    from app.job_sources.queues import InMemoryJobQueue as JobsQueue
    from app.job_sources.runtime import set_service as set_jobs
    from app.job_sources.service import CrawlService

    set_jobs(CrawlService(store=InMemoryJobSourceStore(), queue=JobsQueue()))
    try:
        body = _body(routes.get_settings(_req("GET", "http://localhost/api/v1/settings")))
        assert body["sources"]["greenhouseEnabled"] is False
        assert body["sources"]["leverEnabled"] is False
        assert body["sources"]["greenhouseConfigured"] is False
        assert body["sources"]["leverConfigured"] is False
    finally:
        set_jobs(None)


def test_enable_source_without_tenants_is_source_not_configured(svc, queue):
    from app.job_sources.memory import InMemoryJobSourceStore
    from app.job_sources.queues import InMemoryJobQueue as JobsQueue
    from app.job_sources.runtime import set_service as set_jobs
    from app.job_sources.service import CrawlService

    jobs = CrawlService(store=InMemoryJobSourceStore(), queue=JobsQueue())
    set_jobs(jobs)
    try:
        resp = routes.patch_settings(
            _req(
                "PATCH",
                "http://localhost/api/v1/settings",
                json_body={"sources": {"greenhouseEnabled": True}},
            )
        )
        assert resp.status_code == 400
        body = _body(resp)
        assert body["error"]["code"] == "SOURCE_NOT_CONFIGURED"
        assert "not configured" in body["error"]["message"].lower()
        assert "board" in body["error"]["message"].lower()
        got = _body(routes.get_settings(_req("GET", "http://localhost/api/v1/settings")))
        assert got["sources"]["greenhouseEnabled"] is False
        assert got["sources"]["greenhouseConfigured"] is False
        assert queue.of("source-discovery") == []
        assert jobs.store.list_tenants("greenhouse") == []
    finally:
        set_jobs(None)


def test_enable_source_with_tenants_still_toggles(svc, queue):
    from app.job_sources.memory import InMemoryJobSourceStore
    from app.job_sources.queues import InMemoryJobQueue as JobsQueue
    from app.job_sources.runtime import set_service as set_jobs
    from app.job_sources.service import CrawlService

    jobs = CrawlService(store=InMemoryJobSourceStore(), queue=JobsQueue())
    jobs.store.upsert_tenant("greenhouse", "acme", config={"board_token": "acme"})
    set_jobs(jobs)
    try:
        on = routes.patch_settings(
            _req(
                "PATCH",
                "http://localhost/api/v1/settings",
                json_body={"sources": {"greenhouseEnabled": True}},
            )
        )
        assert on.status_code == 200
        body = _body(on)
        assert body["sources"]["greenhouseEnabled"] is True
        assert body["sources"]["greenhouseConfigured"] is True
        assert body["sources"]["leverConfigured"] is False
        tenants = jobs.store.list_tenants("greenhouse")
        assert tenants and all(item.enabled for item in tenants)
        assert queue.of("source-discovery") == [{"userId": USER, "source": "greenhouse"}]
    finally:
        set_jobs(None)


def test_add_tenant_then_enable_source(svc, queue):
    from app.features import source_ingestion as jobs_routes
    from app.job_sources.memory import InMemoryJobSourceStore
    from app.job_sources.queues import InMemoryJobQueue as JobsQueue
    from app.job_sources.runtime import set_service as set_jobs
    from app.job_sources.service import CrawlService

    jobs = CrawlService(store=InMemoryJobSourceStore(), queue=JobsQueue())
    set_jobs(jobs)
    try:
        created = jobs_routes.create_source_tenant(
            _req(
                "POST",
                "http://localhost/api/v1/sources/greenhouse/tenants",
                json_body={"boardToken": "acme"},
                route={"id": "greenhouse"},
            )
        )
        assert created.status_code == 201
        got = _body(routes.get_settings(_req("GET", "http://localhost/api/v1/settings")))
        assert got["sources"]["greenhouseConfigured"] is True
        assert got["sources"]["greenhouseEnabled"] is False
        assert got["sources"]["leverConfigured"] is False
        blocked = routes.patch_settings(
            _req(
                "PATCH",
                "http://localhost/api/v1/settings",
                json_body={"sources": {"leverEnabled": True}},
            )
        )
        assert blocked.status_code == 400
        assert _body(blocked)["error"]["code"] == "SOURCE_NOT_CONFIGURED"
        on = routes.patch_settings(
            _req(
                "PATCH",
                "http://localhost/api/v1/settings",
                json_body={"sources": {"greenhouseEnabled": True}},
            )
        )
        assert on.status_code == 200
        body = _body(on)
        assert body["sources"]["greenhouseEnabled"] is True
        assert body["sources"]["greenhouseConfigured"] is True
        tenants = jobs.store.list_tenants("greenhouse")
        assert tenants and all(item.enabled for item in tenants)
        assert all(item.tenant_key == "acme" for item in tenants)
    finally:
        set_jobs(None)


def test_unknown_source_is_400(svc):
    resp = routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"sources": {"fooEnabled": True}})
    )
    assert resp.status_code == 400


def test_email_connect_returns_pkce_url(svc):
    resp = routes.connect_email(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/connect",
            json_body={"redirectUri": "http://localhost:5173/callback"},
        )
    )
    assert resp.status_code == 200
    body = _body(resp)
    assert body["state"]
    assert "code_challenge" in body["authUrl"]
    assert "code_challenge_method=S256" in body["authUrl"]
    assert "offline_access" in body["authUrl"]
    pending = _body(routes.get_settings(_req("GET", "http://localhost/api/v1/settings")))
    assert pending["emailConnection"]["status"] == "pending"
    assert pending["oauthConfigured"] is True


def test_get_reports_oauth_unconfigured_when_env_missing(monkeypatch, queue, exchanger):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    monkeypatch.delenv("MICROSOFT_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    service = SettingsService(store=InMemorySettingsStore(), queue=queue, exchanger=exchanger)
    set_service(service)
    try:
        body = _body(routes.get_settings(_req("GET", "http://localhost/api/v1/settings")))
        assert body["oauthConfigured"] is False
        assert body["emailConnection"]["status"] == "disconnected"
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_connect_without_oauth_env_is_oauth_not_configured(monkeypatch, queue, exchanger):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "  ")
    monkeypatch.delenv("MICROSOFT_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    store = InMemorySettingsStore()
    service = SettingsService(store=store, queue=queue, exchanger=exchanger)
    set_service(service)
    try:
        resp = routes.connect_email(
            _req(
                "POST",
                "http://localhost/api/v1/settings/email/connect",
                json_body={"redirectUri": "http://localhost:3000/oauth-callback.html"},
            )
        )
        assert resp.status_code == 400
        body = _body(resp)
        assert body["error"]["code"] == "OAUTH_NOT_CONFIGURED"
        assert "Microsoft OAuth is not configured" in body["error"]["message"]
        assert body["error"].get("details") in (None, [])
        assert store.get_active_connection(USER) is None
        got = _body(routes.get_settings(_req("GET", "http://localhost/api/v1/settings")))
        assert got["oauthConfigured"] is False
        assert got["emailConnection"]["status"] == "disconnected"
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_connect_without_client_secret_is_oauth_not_configured(monkeypatch, queue, exchanger):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client-1")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "")
    get_settings.cache_clear()
    service = SettingsService(store=InMemorySettingsStore(), queue=queue, exchanger=exchanger)
    set_service(service)
    try:
        resp = routes.connect_email(
            _req(
                "POST",
                "http://localhost/api/v1/settings/email/connect",
                json_body={"redirectUri": "https://ajas.example/callback"},
            )
        )
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "OAUTH_NOT_CONFIGURED"
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_email_callback_stores_encrypted_refresh(svc, exchanger):
    connected = routes.connect_email(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/connect",
            json_body={"redirectUri": "https://ajas.example/callback"},
        )
    )
    state = _body(connected)["state"]
    resp = routes.email_callback(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/callback",
            json_body={"code": "abc", "state": state, "redirectUri": "https://ajas.example/callback"},
        )
    )
    assert resp.status_code == 200
    body = _body(resp)
    assert body["emailConnection"]["status"] == "connected"
    assert body["emailConnection"]["provider"] == "microsoft"
    assert body["emailConnection"]["accountId"] == "jane@contoso.com"
    dumped = json.dumps(body)
    assert REFRESH not in dumped
    assert "access-token" not in dumped
    stored = svc.store.get_active_connection(USER)
    assert stored is not None
    assert stored.refresh_token_enc
    assert REFRESH not in stored.refresh_token_enc
    assert exchanger.calls and exchanger.calls[0]["code"] == "abc"


def test_email_callback_invalid_state_is_400(svc):
    resp = routes.email_callback(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/callback",
            json_body={"code": "abc", "state": "nope", "redirectUri": "https://ajas.example/callback"},
        )
    )
    assert resp.status_code == 400


def test_email_callback_graph_error_sets_error_status(svc, monkeypatch, queue):
    failing = FakeExchanger(fail=True)
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client-1")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret-1")
    get_settings.cache_clear()
    service = SettingsService(store=InMemorySettingsStore(), queue=queue, exchanger=failing)
    set_service(service)
    connected = routes.connect_email(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/connect",
            json_body={"redirectUri": "https://ajas.example/callback"},
        )
    )
    state = _body(connected)["state"]
    resp = routes.email_callback(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/callback",
            json_body={"code": "bad", "state": state, "redirectUri": "https://ajas.example/callback"},
        )
    )
    assert resp.status_code == 502
    got = _body(routes.get_settings(_req("GET", "http://localhost/api/v1/settings")))
    assert got["emailConnection"]["status"] == "error"


def test_connect_when_connected_is_noop(svc):
    start = routes.connect_email(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/connect",
            json_body={"redirectUri": "https://ajas.example/callback"},
        )
    )
    state = _body(start)["state"]
    routes.email_callback(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/callback",
            json_body={"code": "abc", "state": state, "redirectUri": "https://ajas.example/callback"},
        )
    )
    again = routes.connect_email(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/connect",
            json_body={"redirectUri": "https://ajas.example/callback"},
        )
    )
    assert again.status_code == 200
    assert _body(again)["noOp"] is True


def test_disconnect_is_idempotent(svc):
    start = routes.connect_email(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/connect",
            json_body={"redirectUri": "https://ajas.example/callback"},
        )
    )
    state = _body(start)["state"]
    routes.email_callback(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/callback",
            json_body={"code": "abc", "state": state, "redirectUri": "https://ajas.example/callback"},
        )
    )
    first = routes.disconnect_email(_req("POST", "http://localhost/api/v1/settings/email/disconnect"))
    assert first.status_code == 200
    assert _body(first)["emailConnection"]["status"] == "disconnected"
    second = routes.disconnect_email(_req("POST", "http://localhost/api/v1/settings/email/disconnect"))
    assert second.status_code == 200
    assert _body(second)["emailConnection"]["status"] == "disconnected"
    got = _body(routes.get_settings(_req("GET", "http://localhost/api/v1/settings")))
    assert got["emailConnection"]["status"] == "disconnected"
    assert REFRESH not in json.dumps(got)


def test_write_rate_limit(svc):
    for _ in range(10):
        resp = routes.patch_settings(
            _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": 0.5})
        )
        assert resp.status_code == 200
    limited = routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"matchThreshold": 0.51})
    )
    assert limited.status_code == 429


def test_connect_rate_limit(svc):
    for _ in range(3):
        resp = routes.connect_email(
            _req(
                "POST",
                "http://localhost/api/v1/settings/email/connect",
                json_body={"redirectUri": "http://localhost:5173/callback"},
            )
        )
        assert resp.status_code == 200
    limited = routes.connect_email(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/connect",
            json_body={"redirectUri": "http://localhost:5173/callback"},
        )
    )
    assert limited.status_code == 429


def test_non_localhost_http_redirect_is_rejected(svc):
    resp = routes.connect_email(
        _req(
            "POST",
            "http://localhost/api/v1/settings/email/connect",
            json_body={"redirectUri": "http://evil.example/callback"},
        )
    )
    assert resp.status_code == 400


def test_jwt_claims_extracts_account_without_raw_token():
    import base64

    from app.settings.oauth import jwt_claims

    payload = base64.urlsafe_b64encode(
        json.dumps({"preferred_username": "jane@contoso.com", "tid": "tenant-1"}).encode()
    ).rstrip(b"=").decode()
    token = f"eyJhbGciOiJub25lIn0.{payload}.sig"
    claims = jwt_claims(token)
    assert claims["preferred_username"] == "jane@contoso.com"
    assert claims["tid"] == "tenant-1"


def test_microsoft_oauth_configured_requires_id_and_secret(monkeypatch):
    from app.config import microsoft_oauth_configured

    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    monkeypatch.delenv("MICROSOFT_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    assert microsoft_oauth_configured() is False
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client-1")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "  ")
    get_settings.cache_clear()
    assert microsoft_oauth_configured() is False
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret-1")
    get_settings.cache_clear()
    assert microsoft_oauth_configured() is True
    get_settings.cache_clear()

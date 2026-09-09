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
) -> func.HttpRequest:
    headers = {}
    body = b""
    if user:
        headers["Authorization"] = f"Bearer {user}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode()
    return func.HttpRequest(method=method, url=url, headers=headers, params={}, route_params={}, body=body)


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    return json.loads(raw) if raw else None


def test_function_app_registers_settings_routes(function_names):
    assert "get_settings" in function_names
    assert "patch_settings" in function_names
    assert "connect_email" in function_names
    assert "email_callback" in function_names
    assert "disconnect_email" in function_names
    assert "health" in function_names


def test_unauthenticated_is_401(svc):
    resp = routes.get_settings(_req("GET", "http://localhost/api/v1/settings", user=None))
    assert resp.status_code == 401


def test_get_defaults_without_secrets(svc):
    resp = routes.get_settings(_req("GET", "http://localhost/api/v1/settings"))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["matchThreshold"] == 0.7
    assert body["sources"] == {"greenhouseEnabled": False, "leverEnabled": False}
    assert body["emailConnection"]["status"] == "disconnected"
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

"""IMAP/SMTP extra-mail connector: fixtures, RFC822, UID cursor, live fail-closed."""

from __future__ import annotations

import json
from pathlib import Path

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import integrations as routes
from app.integrations.imap import (
    ImapMessage,
    LiveImapError,
    LocalImapClient,
    clear_credentials,
    clear_live_transport,
    fetch_via_imaplib,
    live_connect_guard,
    live_fetch_allowed,
    remember_credentials,
    send_mail,
    set_live_transport,
    sync_inbox,
)
from app.integrations.imap_spec import API_CONTRACT, RATE_PLAN, parse_rfc822, spec_bundle, unwrap_imap_payload
from app.integrations.service import reset_service
from app.job_sources.constants import SOURCE_TYPES

FIXTURES = Path(__file__).parent / "fixtures" / "mail"
USER = "user-1"


def _req(method: str, url: str, *, params=None, body=None, route_params=None):
    payload = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    return func.HttpRequest(
        method=method,
        url=url,
        headers={"Authorization": f"Bearer {USER}"},
        params=params or {},
        route_params=route_params or {},
        body=payload,
    )


@pytest.fixture(autouse=True)
def _clean():
    reset_service()
    clear_credentials()
    clear_live_transport()
    get_settings.cache_clear()
    yield
    reset_service()
    clear_credentials()
    clear_live_transport()
    get_settings.cache_clear()


def test_imap_flag_defaults_on_without_live_sockets():
    from app.flags import feature_enabled
    from app.mail.imap_health import imap_health
    from app.mail.outlook import outlook_status

    assert feature_enabled("imap_transport") is True
    health = imap_health()
    assert health["transport"] == "graph"
    assert health["imapConfigured"] is False
    assert health["liveFetch"] is False
    assert health["status"] == "not_configured"
    outlook = outlook_status()
    assert outlook["graph"] is True
    assert outlook["imap"] is False
    assert outlook["imapEnabled"] is True
    assert live_fetch_allowed() is False
    assert SOURCE_TYPES == frozenset({"greenhouse", "lever"})


def test_imap_sync_json_rfc822_and_send(monkeypatch):
    monkeypatch.setenv("FLAG_IMAP_TRANSPORT", "true")
    get_settings.cache_clear()
    payload = json.loads((FIXTURES / "imap_inbox.json").read_text())
    client = LocalImapClient()
    synced = sync_inbox("acct-1", client=client, payload=payload)
    assert synced["reason"] == "ok"
    assert synced["liveFetch"] is False
    assert len(synced["items"]) == 2
    interview = next(item for item in synced["items"] if item["id"] == "11")
    assert interview["from"] == "maya@acme.test"
    assert interview["state"] == "open"
    assert any(thread["intent"] == "interview" for thread in synced["threads"])
    rfc = (FIXTURES / "imap_rfc822.eml").read_text()
    parsed = parse_rfc822(rfc)
    assert parsed["from"] == "maya@acme.test"
    assert "phone screen" in parsed["body"]
    rfc_sync = sync_inbox("acct-rfc", payload=rfc)
    assert rfc_sync["items"][0]["subject"] == "Interview availability"
    sent = send_mail("acct-1", to_addresses=["maya@acme.test"], subject="Interview availability", body_text="Tue 10am works.", thread_id="<imap-1@acme.test>", client=client)
    assert sent["reason"] == "ok"
    assert sent["threadId"] == "<imap-1@acme.test>"
    assert sent["folder"] == "Sent"
    envelope = unwrap_imap_payload(
        {
            "uid": "21",
            "envelope": {
                "subject": "Staff Platform Engineer",
                "from": "jordan@initech.test",
                "to": ["alex@ajas.dev"],
                "date": "Sun, 01 Mar 2026 12:00:00 +0000",
            },
            "body": "Following up on your application.",
            "folder": "INBOX",
        }
    )
    assert envelope["messages"][0]["from"] == "jordan@initech.test"
    env_sync = sync_inbox(
        "acct-env",
        payload={
            "uid": "21",
            "envelope": {
                "subject": "Staff Platform Engineer",
                "from": "jordan@initech.test",
                "to": ["alex@ajas.dev"],
                "date": "Sun, 01 Mar 2026 12:00:00 +0000",
            },
            "body": "Following up on your application.",
            "folder": "INBOX",
        },
    )
    assert env_sync["items"][0]["from"] == "jordan@initech.test"
    client_cursor = LocalImapClient()
    first = sync_inbox("acct-uid", client=client_cursor, payload=payload)
    assert first["cursor"] == "12"
    later = sync_inbox("acct-uid", client=client_cursor, since_uid="11")
    assert [item["id"] for item in later["items"]] == ["12"]
    pages = sync_inbox(
        "acct-pages",
        payload={
            "pages": [
                {"messages": [payload["messages"][0]]},
                {"messages": [payload["messages"][1]]},
            ]
        },
    )
    assert pages["cursor"] == "12"
    monkeypatch.setenv("FLAG_IMAP_TRANSPORT", "false")
    get_settings.cache_clear()
    assert sync_inbox("acct-1", payload=payload)["reason"] == "flag_off"


def test_imap_live_fetch_fail_closed(monkeypatch):
    monkeypatch.setenv("FLAG_IMAP_TRANSPORT", "true")
    get_settings.cache_clear()
    live = sync_inbox("acct-1", live=True)
    assert live["reason"] == "needs_auth"
    assert live["bypass"] is False
    remember_credentials(host="imap.example.test", username="ada", password="secret")
    gated = live_connect_guard()
    assert gated["reason"] == "live_disabled"
    monkeypatch.setenv("IMAP_LIVE", "true")
    monkeypatch.setenv("IMAP_HOST", "imap.example.test")
    monkeypatch.setenv("IMAP_USERNAME", "ada")
    monkeypatch.setenv("IMAP_PASSWORD", "secret")
    monkeypatch.setenv("IMAP_USE_SSL", "false")
    monkeypatch.setenv("IMAP_ALLOWED_HOSTS", "imap.example.test")
    get_settings.cache_clear()
    assert live_fetch_allowed() is False
    monkeypatch.setenv("IMAP_USE_SSL", "true")
    get_settings.cache_clear()
    remember_credentials(host="imap.example.test", username="ada", password="secret")
    assert live_fetch_allowed() is True
    set_live_transport(
        fetch=lambda **_: [
            ImapMessage(
                uid="31",
                message_id="<live-1@acme.test>",
                thread_id="<live-1@acme.test>",
                subject="Interview availability",
                from_address="maya@acme.test",
                from_name="Maya Recruiter",
                to_addresses=["alex@ajas.dev"],
                body_text="Could we schedule a phone screen this week?",
                received_at="2026-03-01T12:00:00Z",
            )
        ],
        send=lambda **kw: ImapMessage(
            uid="32",
            message_id="<sent-live@ajas.dev>",
            thread_id=str(kw.get("thread_id") or "t-live"),
            subject=str(kw.get("subject") or ""),
            from_address="ada@ajas.dev",
            from_name="AJAS",
            to_addresses=list(kw.get("to_addresses") or []),
            body_text=str(kw.get("body_text") or ""),
            received_at="2026-03-01T12:00:00Z",
            folder="Sent",
        ),
    )
    live_ok = sync_inbox("acct-live", live=True)
    assert live_ok["liveFetch"] is True
    assert live_ok["items"][0]["from"] == "maya@acme.test"
    sent_live = send_mail("acct-live", to_addresses=["maya@acme.test"], subject="Re: Interview", body_text="Tue works.", live=True)
    assert sent_live["liveFetch"] is True
    assert sent_live["folder"] == "Sent"
    with pytest.raises(LiveImapError):
        clear_credentials()
        monkeypatch.delenv("IMAP_USERNAME", raising=False)
        monkeypatch.delenv("IMAP_PASSWORD", raising=False)
        get_settings.cache_clear()
        fetch_via_imaplib()
    bundle = spec_bundle()
    assert bundle["api"]["emailPrdTransport"] == "microsoft-graph"
    assert bundle["api"]["liveFetch"] == "opt-in-allowlisted-ssl"
    assert API_CONTRACT["publicSearchApi"] is False
    assert RATE_PLAN["ingest"]["capPerWindow"] == 20
    assert "password" not in str(bundle).lower() or "IMAP_PASSWORD" in str(bundle.get("security"))


def test_imap_http_routes(monkeypatch):
    monkeypatch.setenv("FLAG_IMAP_TRANSPORT", "true")
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    reset_service()
    payload = json.loads((FIXTURES / "imap_inbox.json").read_text())
    synced = json.loads(
        routes.integrations_imap_sync(
            _req("POST", "http://localhost/api/v1/integrations/imap/sync", body={"payload": payload})
        ).get_body()
    )
    assert synced["reason"] == "ok"
    assert synced["items"]
    rfc = json.loads(
        routes.integrations_imap_sync(
            _req("POST", "http://localhost/api/v1/integrations/imap/sync", body=(FIXTURES / "imap_rfc822.eml").read_bytes())
        ).get_body()
    )
    assert rfc["items"][0]["subject"] == "Interview availability"
    sent = json.loads(
        routes.integrations_imap_send(
            _req(
                "POST",
                "http://localhost/api/v1/integrations/imap/send",
                body={"to": ["maya@acme.test"], "subject": "Interview availability", "body": "Tue works."},
            )
        ).get_body()
    )
    assert sent["id"]
    spec = json.loads(routes.integrations_imap_spec(_req("GET", "http://localhost/api/v1/integrations/imap/spec")).get_body())
    assert spec["flag"] == "imap_transport"
    live = json.loads(
        routes.integrations_imap_sync(
            _req("POST", "http://localhost/api/v1/integrations/imap/sync", body={"live": True})
        ).get_body()
    )
    assert live["reason"] == "needs_auth"
    unauth = func.HttpRequest(method="GET", url="http://localhost/api/v1/integrations/imap/spec", headers={}, params={}, body=b"")
    assert routes.integrations_imap_spec(unauth).status_code == 401
    monkeypatch.setenv("FLAG_IMAP_TRANSPORT", "false")
    get_settings.cache_clear()
    reset_service()
    off = json.loads(
        routes.integrations_imap_sync(_req("POST", "http://localhost/api/v1/integrations/imap/sync", body={"payload": payload})).get_body()
    )
    assert off["reason"] == "flag_off"

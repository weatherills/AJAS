"""Email Ingestion Backend PRD — HTTP API, webhook, reply, suggestions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import email as routes
from app.mail.graph import GraphAttachment, GraphMessage, LocalGraphClient
from app.mail.keys import utc_now
from app.mail.memory import InMemoryEmailStore
from app.mail.queues import InMemoryJobQueue
from app.mail.runtime import set_service
from app.mail.service import EmailService
from app.settings.memory import InMemorySettingsStore
from app.settings.models import EmailConnection

USER = "user-1"


@pytest.fixture
def store():
    return InMemoryEmailStore(seed=False)


@pytest.fixture
def queue():
    return InMemoryJobQueue()


@pytest.fixture
def graph():
    return LocalGraphClient()


@pytest.fixture
def settings_store():
    return InMemorySettingsStore()


@pytest.fixture
def svc(monkeypatch, store, queue, graph, settings_store):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    get_settings.cache_clear()
    service = EmailService(
        store=store, queue=queue, graph=graph, local_mode=True, settings_store=settings_store
    )
    set_service(service)
    yield service
    set_service(None)
    get_settings.cache_clear()


def _graph_connection(user_id: str = USER, **overrides) -> EmailConnection:
    now = utc_now()
    expires = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    payload = {
        "user_id": user_id,
        "provider": "microsoft_365",
        "status": "active",
        "account_email": "jane@contoso.com",
        "access_token_enc": "enc:access",
        "refresh_token_enc": "enc:refresh",
        "expires_at": expires,
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return EmailConnection.model_validate(payload)


def _req(
    method: str,
    url: str,
    *,
    user: str | None = USER,
    json_body=None,
    params: dict | None = None,
    route: dict | None = None,
    headers: dict | None = None,
    body: bytes | None = None,
) -> func.HttpRequest:
    hdrs = dict(headers or {})
    raw = body or b""
    if user:
        hdrs["Authorization"] = f"Bearer {user}"
    if json_body is not None:
        hdrs["Content-Type"] = "application/json"
        raw = json.dumps(json_body).encode()
    return func.HttpRequest(
        method=method,
        url=url,
        headers=hdrs,
        params=params or {},
        route_params=route or {},
        body=raw,
    )


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode()


def test_function_app_registers_email_routes(function_names):
    assert "graph_mail_webhook" in function_names
    assert "list_job_email_threads" in function_names
    assert "list_thread_messages" in function_names
    assert "reply_thread" in function_names
    assert "suggest_thread_replies" in function_names
    assert "mail_ingest_job" in function_names
    assert "email_status" in function_names
    assert "health" in function_names


def test_unauthenticated_is_401(svc):
    resp = routes.email_status(_req("GET", "http://localhost/api/v1/email/status", user=None))
    assert resp.status_code == 401
    assert _body(resp)["error"]["code"] == "UNAUTHENTICATED"


def test_local_status_without_oauth_is_demo_not_graph(svc):
    resp = routes.email_status(_req("GET", "http://localhost/api/v1/email/status"))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["connected"] is False
    assert body["graphConnected"] is False
    assert body["demo"] is True
    assert body["provider"] == "demo"
    assert body["address"]
    threads = routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads"))
    assert threads.status_code == 200
    assert _body(threads)["total"] > 0


def test_status_with_graph_oauth_is_connected(svc, settings_store):
    settings_store.get_or_create_settings(USER, actor_id=USER)
    settings_store.upsert_connection(USER, _graph_connection(), actor_id=USER)
    resp = routes.email_status(_req("GET", "http://localhost/api/v1/email/status"))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["connected"] is True
    assert body["graphConnected"] is True
    assert body["demo"] is False
    assert body["provider"] == "microsoft365"
    assert body["address"] == "jane@contoso.com"


def test_status_without_graph_outside_local_mode(store, queue, graph, settings_store, monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    get_settings.cache_clear()
    service = EmailService(
        store=store, queue=queue, graph=graph, local_mode=False, settings_store=settings_store
    )
    set_service(service)
    try:
        resp = routes.email_status(_req("GET", "http://localhost/api/v1/email/status"))
        assert resp.status_code == 200
        body = _body(resp)
        assert body["connected"] is False
        assert body["graphConnected"] is False
        assert body["demo"] is False
        assert body["provider"] is None
        assert body["address"] is None
        listed = routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads"))
        assert listed.status_code == 401
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_webhook_validation_token_echoed(svc):
    resp = routes.graph_mail_webhook(
        _req(
            "POST",
            "http://localhost/api/webhooks/graph/mail",
            user=None,
            params={"validationToken": "abc-123"},
        )
    )
    assert resp.status_code == 200
    assert resp.get_body().decode() == "abc-123"
    assert resp.mimetype == "text/plain"


def test_webhook_invalid_client_state_is_401(svc):
    resp = routes.graph_mail_webhook(
        _req(
            "POST",
            "http://localhost/api/webhooks/graph/mail",
            user=None,
            json_body={"value": [{"clientState": "nope", "resourceData": {"id": "m1"}}]},
        )
    )
    assert resp.status_code == 401


def test_webhook_accepted_and_dedupes(svc, graph, store):
    account = store.seed_demo_mailbox(USER, jobs=[{"id": "job-staff", "title": "Staff Engineer", "company": "Acme"}])
    inbound = GraphMessage(
        id="graph-new-1",
        internet_message_id="<new-1@acme.test>",
        conversation_id="conv-staff-acme",
        subject="Re: Staff Engineer at Acme (JOB-SE-1)",
        from_address="maya@acme.test",
        from_name="Maya Chen",
        to_addresses=[account.address],
        body_text="Thursday works — talk then.",
        received_at=utc_now(),
    )
    graph.put(account.id, inbound)
    payload = {
        "value": [
            {
                "clientState": "dev-mail-webhook",
                "changeType": "created",
                "resourceData": {"id": "graph-new-1"},
            }
        ]
    }
    resp = routes.graph_mail_webhook(
        _req("POST", "http://localhost/api/webhooks/graph/mail", user=None, json_body=payload)
    )
    assert resp.status_code == 202
    messages = store.list_messages(store.get_thread_by_conversation(account.id, "conv-staff-acme").id)
    assert any(item.graph_message_id == "graph-new-1" for item in messages)
    resp2 = routes.graph_mail_webhook(
        _req("POST", "http://localhost/api/webhooks/graph/mail", user=None, json_body=payload)
    )
    assert resp2.status_code == 202
    assert sum(1 for item in store.list_messages(messages[0].email_thread_id) if item.graph_message_id == "graph-new-1") == 1


def test_unlinked_when_no_job_tokens(svc, graph, store):
    account = store.ensure_account(USER, address="user-1@ajas.dev", demo=True)
    inbound = GraphMessage(
        id="graph-unk",
        internet_message_id="<unk@x>",
        conversation_id="conv-unk",
        subject="Office snacks survey",
        from_address="hr@random.test",
        from_name="HR",
        to_addresses=[account.address],
        body_text="Please fill this unrelated survey.",
        received_at=utc_now(),
    )
    graph.put(account.id, inbound)
    svc.process_ingest({"kind": "webhook", "accountId": account.id, "graphMessageId": "graph-unk"})
    thread = store.get_thread_by_conversation(account.id, "conv-unk")
    assert thread is not None
    assert thread.job_posting_id is None


def test_list_threads_and_messages_marks_read(svc, store):
    store.seed_demo_mailbox(USER, jobs=[{"id": "job-staff", "title": "Staff Engineer", "company": "Acme"}])
    listed = routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads"))
    assert listed.status_code == 200
    items = _body(listed)["items"]
    assert items
    unread = next(item for item in items if item["unreadCount"] > 0)
    resp = routes.list_thread_messages(
        _req(
            "GET",
            f"http://localhost/api/v1/threads/{unread['id']}/messages",
            route={"threadId": unread["id"]},
        )
    )
    assert resp.status_code == 200
    payload = _body(resp)
    assert payload["items"]
    assert payload["thread"]["unreadCount"] == 0


def test_reply_201_and_idempotency_409(svc, store):
    store.seed_demo_mailbox(USER, jobs=[{"id": "job-staff", "title": "Staff Engineer", "company": "Acme"}])
    thread = _body(routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads")))["items"][0]
    resp = routes.reply_thread(
        _req(
            "POST",
            f"http://localhost/api/v1/threads/{thread['id']}/reply",
            route={"threadId": thread["id"]},
            json_body={"bodyText": "Thanks, Thursday works.", "idempotencyKey": "k1"},
        )
    )
    assert resp.status_code == 201
    assert _body(resp)["deliveryStatus"] == "sent"
    dup = routes.reply_thread(
        _req(
            "POST",
            f"http://localhost/api/v1/threads/{thread['id']}/reply",
            route={"threadId": thread["id"]},
            json_body={"bodyText": "Thanks, Thursday works.", "idempotencyKey": "k1"},
        )
    )
    assert dup.status_code == 409


def test_reply_unfilled_template_is_422(svc, store):
    store.seed_demo_mailbox(USER, jobs=[{"id": "job-staff", "title": "Staff Engineer", "company": "Acme"}])
    thread = _body(routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads")))["items"][0]
    resp = routes.reply_thread(
        _req(
            "POST",
            f"http://localhost/api/v1/threads/{thread['id']}/reply",
            route={"threadId": thread["id"]},
            json_body={"templateId": "thanks", "variables": {"firstName": "Maya"}},
        )
    )
    assert resp.status_code == 422


def test_reply_missing_thread_is_404(svc, store):
    store.ensure_account(USER, address="user-1@ajas.dev", demo=True)
    resp = routes.reply_thread(
        _req(
            "POST",
            "http://localhost/api/v1/threads/missing/reply",
            route={"threadId": "missing"},
            json_body={"bodyText": "Hi"},
        )
    )
    assert resp.status_code == 404


def test_suggestions_three_drafts_and_rate_limit(svc, store, monkeypatch):
    monkeypatch.setenv("MAIL_SUGGESTION_LIMIT_PER_DAY", "2")
    get_settings.cache_clear()
    store.seed_demo_mailbox(USER, jobs=[{"id": "job-staff", "title": "Staff Engineer", "company": "Acme"}])
    thread = _body(routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads")))["items"][0]
    first = routes.suggest_thread_replies(
        _req(
            "POST",
            f"http://localhost/api/v1/threads/{thread['id']}/suggestions",
            route={"threadId": thread["id"]},
            json_body={"tone": "professional"},
        )
    )
    assert first.status_code == 200
    items = _body(first)["items"]
    assert len(items) == 3
    assert all(len(item["text"].split()) < 500 for item in items)
    routes.suggest_thread_replies(
        _req(
            "POST",
            f"http://localhost/api/v1/threads/{thread['id']}/suggestions",
            route={"threadId": thread["id"]},
            json_body={},
        )
    )
    limited = routes.suggest_thread_replies(
        _req(
            "POST",
            f"http://localhost/api/v1/threads/{thread['id']}/suggestions",
            route={"threadId": thread["id"]},
            json_body={},
        )
    )
    assert limited.status_code == 429


def test_job_threads_and_manual_link(svc, store):
    jobs = svc._jobs()
    payload = [{"id": job.id, "title": job.title, "company": job.company} for job in jobs] or [
        {"id": "job-staff", "title": "Staff Engineer", "company": "Acme"}
    ]
    store.seed_demo_mailbox(USER, jobs=payload)
    staff_id = next((job.id for job in jobs if "staff" in job.title.lower()), payload[0]["id"])
    listed = routes.list_job_email_threads(
        _req("GET", f"http://localhost/api/v1/jobs/{staff_id}/threads", route={"jobId": staff_id})
    )
    assert listed.status_code == 200
    assert all(item["jobId"] == staff_id for item in _body(listed)["items"])
    unlinked = next(
        item
        for item in _body(routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads")))["items"]
        if not item["linked"]
    )
    linked = routes.link_email_thread(
        _req(
            "POST",
            f"http://localhost/api/v1/threads/{unlinked['id']}/link",
            route={"threadId": unlinked["id"]},
            json_body={"jobId": staff_id},
        )
    )
    assert linked.status_code == 200
    assert _body(linked)["jobId"] == staff_id
    assert _body(linked)["linkSource"] == "manual"


def test_oversized_attachment_metadata_only(svc, store, graph):
    account = store.ensure_account(USER, address="user-1@ajas.dev", demo=True)
    inbound = GraphMessage(
        id="graph-att",
        internet_message_id="<att@x>",
        conversation_id="conv-att",
        subject="Staff Engineer at Acme (JOB-SE-1)",
        from_address="maya@acme.test",
        from_name="Maya",
        to_addresses=[account.address],
        body_text="Please see the brief.",
        received_at=utc_now(),
        attachments=[
            GraphAttachment(name="huge.bin", content_type="application/octet-stream", size=11 * 1024 * 1024, content=b"")
        ],
    )
    graph.put(account.id, inbound)
    svc.process_ingest({"kind": "webhook", "accountId": account.id, "graphMessageId": "graph-att"})
    thread = store.get_thread_by_conversation(account.id, "conv-att")
    message = store.list_messages(thread.id)[0]
    atts = store.list_attachments(message.id)
    assert atts[0].status == "skipped_oversize"
    assert atts[0].blob_path is None


def test_refresh_seeds_followup(svc, store):
    store.seed_demo_mailbox(USER, jobs=[{"id": "job-staff", "title": "Staff Engineer", "company": "Acme"}])
    before = _body(routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads")))["total"]
    resp = routes.refresh_email(_req("POST", "http://localhost/api/v1/email/refresh", json_body={}))
    assert resp.status_code == 200
    after = _body(routes.list_email_threads(_req("GET", "http://localhost/api/v1/email/threads")))["total"]
    assert after >= before

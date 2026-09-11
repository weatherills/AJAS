"""PRD Kanban leftovers: Graph HTTP client, subscription create, attachment download."""

from __future__ import annotations

import base64

from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.mail.graph import (
    GraphAttachment,
    HttpGraphClient,
    LocalGraphClient,
    default_graph_client,
)
from app.mail.memory import InMemoryEmailStore
from app.mail.queues import InMemoryJobQueue
from app.mail.service import EmailService
from app.settings.memory import InMemorySettingsStore
from app.settings.models import EmailConnection
from app.mail.keys import utc_now

USER = "user-1"


class FakeGraphHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []

    def request(self, method: str, url: str, *, headers: dict[str, str], body: dict | None = None) -> tuple[int, dict]:
        self.calls.append((method, url, body))
        if method == "GET" and "messages/delta" in url:
            return 200, {
                "value": [
                    {
                        "id": "g1",
                        "internetMessageId": "<g1@acme.test>",
                        "conversationId": "conv-1",
                        "subject": "Staff Engineer at Acme",
                        "from": {"emailAddress": {"address": "maya@acme.test", "name": "Maya"}},
                        "toRecipients": [{"emailAddress": {"address": "jane@contoso.com"}}],
                        "body": {"content": "Please see the brief."},
                        "receivedDateTime": "2026-09-10T00:00:00Z",
                        "isRead": False,
                        "attachments": [
                            {
                                "name": "brief.pdf",
                                "contentType": "application/pdf",
                                "size": 4,
                                "contentBytes": base64.b64encode(b"%PDF").decode("ascii"),
                            }
                        ],
                    }
                ],
                "@odata.deltaLink": "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages/delta?$deltatoken=next",
            }
        if method == "GET" and "/messages/" in url:
            return 200, {
                "id": "g1",
                "subject": "Staff Engineer at Acme",
                "from": {"emailAddress": {"address": "maya@acme.test", "name": "Maya"}},
                "body": {"content": "Please see the brief."},
            }
        if method == "POST" and url.endswith("/sendMail"):
            return 202, {}
        if method == "POST" and url.endswith("/subscriptions"):
            return 201, {
                "id": "sub-graph-1",
                "resource": "/me/messages",
                "expirationDateTime": "2026-09-12T00:00:00Z",
            }
        if method == "PATCH" and "/subscriptions/" in url:
            return 200, {"id": "sub-graph-1", "expirationDateTime": "2026-09-13T00:00:00Z"}
        return 500, {"error": "unexpected"}


def test_default_graph_client_is_local_without_oauth(monkeypatch):
    monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
    monkeypatch.delenv("MICROSOFT_CLIENT_SECRET", raising=False)
    get_settings.cache_clear()
    try:
        assert isinstance(default_graph_client(), LocalGraphClient)
    finally:
        get_settings.cache_clear()


def test_default_graph_client_uses_http_when_oauth_configured(monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client-1")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret-1")
    get_settings.cache_clear()
    try:
        assert isinstance(default_graph_client(), HttpGraphClient)
    finally:
        get_settings.cache_clear()


def test_http_graph_client_retries_once_after_401():
    class UnauthorizedThenOk(FakeGraphHttp):
        def __init__(self) -> None:
            super().__init__()
            self._unauth = True

        def request(self, method: str, url: str, *, headers: dict[str, str], body: dict | None = None) -> tuple[int, dict]:
            if self._unauth:
                self._unauth = False
                self.calls.append((method, url, body))
                return 401, {"error": "expired"}
            return super().request(method, url, headers=headers, body=body)

    tokens: list[str] = []

    def provider() -> str:
        token = f"tok-{len(tokens)}"
        tokens.append(token)
        return token

    http = UnauthorizedThenOk()
    client = HttpGraphClient(token_provider=provider, http=http)
    fetched = client.fetch_message("acct-1", "g1")
    assert fetched is not None
    assert fetched.subject == "Staff Engineer at Acme"
    assert tokens == ["tok-0", "tok-1"]
    assert http.calls[0][0] == "GET"
    assert http.calls[1][0] == "GET"


def test_http_graph_client_fetch_delta_send_and_subscribe():
    http = FakeGraphHttp()
    client = HttpGraphClient(token_provider=lambda: "tok", http=http)
    fetched = client.fetch_message("acct-1", "g1")
    assert fetched is not None
    assert fetched.subject == "Staff Engineer at Acme"
    messages, token = client.delta("acct-1", None)
    assert len(messages) == 1
    assert messages[0].attachments[0].name == "brief.pdf"
    assert messages[0].attachments[0].content == b"%PDF"
    assert "deltatoken=next" in token
    sent = client.send_reply(
        "acct-1",
        conversation_id="conv-1",
        internet_message_id="<g1@acme.test>",
        subject="Staff Engineer at Acme",
        body_text="Thanks Maya",
        to_addresses=["maya@acme.test"],
        attachments=[GraphAttachment(name="cv.pdf", content_type="application/pdf", size=3, content=b"cv1")],
    )
    assert sent.body_text == "Thanks Maya"
    send = next(call for call in http.calls if call[0] == "POST" and call[1].endswith("/sendMail"))
    assert send[2]["message"]["attachments"][0]["name"] == "cv.pdf"
    created = client.create_subscription(
        notification_url="https://ajas.example/api/webhooks/graph/mail",
        client_state="secret",
    )
    assert created["id"] == "sub-graph-1"
    renewed = client.create_subscription(
        notification_url="https://ajas.example/api/webhooks/graph/mail",
        client_state="secret",
        existing_id="sub-graph-1",
    )
    assert renewed["id"] == "sub-graph-1"
    assert any(call[0] == "PATCH" for call in http.calls)


def test_ensure_graph_subscription_persists_local_row():
    store = InMemoryEmailStore(seed=False)
    settings_store = InMemorySettingsStore()
    now = utc_now()
    expires = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    settings_store.upsert_connection(
        USER,
        EmailConnection.model_validate(
            {
                "user_id": USER,
                "provider": "microsoft_365",
                "status": "active",
                "account_email": "jane@contoso.com",
                "access_token_enc": "enc:access",
                "refresh_token_enc": "enc:refresh",
                "expires_at": expires,
                "created_at": now,
                "updated_at": now,
            }
        ),
        actor_id=USER,
    )
    graph = LocalGraphClient()
    svc = EmailService(
        store=store,
        queue=InMemoryJobQueue(),
        graph=graph,
        local_mode=True,
        settings_store=settings_store,
    )
    from app.settings.runtime import set_service as set_settings
    from app.settings.queues import InMemoryJobQueue as SettingsQueue
    from app.settings.service import SettingsService

    set_settings(SettingsService(store=settings_store, queue=SettingsQueue()))
    try:
        row = svc.ensure_graph_subscription(USER)
        assert row is not None
        assert store.get_subscription(store.get_account_for_user(USER).id).graph_subscription_id == row.graph_subscription_id
        saved = settings_store.get_active_connection(USER)
        assert saved is not None
        assert saved.webhook_subscription_id == row.graph_subscription_id
        assert graph._subscriptions
    finally:
        set_settings(None)


class RefreshExchanger:
    def __init__(self) -> None:
        self.calls = 0

    def refresh(self, *, refresh_token: str):
        from app.settings.oauth import TokenSet

        self.calls += 1
        assert refresh_token == "refresh-plain"
        return TokenSet(
            access_token="fresh-access",
            refresh_token="refresh-plain-2",
            expires_in=3600,
            scope="offline_access Mail.Read Mail.Send",
        )


def test_graph_access_token_refreshes_when_expired():
    from app.settings.crypto import open_token
    from app.settings.queues import InMemoryJobQueue as SettingsQueue
    from app.settings.runtime import set_service as set_settings
    from app.settings.service import SettingsService

    store = InMemorySettingsStore()
    now = utc_now()
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    store.upsert_connection(
        USER,
        EmailConnection.model_validate(
            {
                "user_id": USER,
                "provider": "microsoft_365",
                "status": "active",
                "account_email": "jane@contoso.com",
                "access_token_enc": "stale-access",
                "refresh_token_enc": "refresh-plain",
                "expires_at": past,
                "created_at": now,
                "updated_at": now,
            }
        ),
        actor_id=USER,
    )
    exchanger = RefreshExchanger()
    service = SettingsService(store=store, queue=SettingsQueue(), exchanger=exchanger)
    set_settings(service)
    get_settings.cache_clear()
    try:
        token = service.graph_access_token(USER)
        assert token == "fresh-access"
        assert exchanger.calls == 1
        saved = store.get_active_connection(USER)
        assert open_token(saved.access_token_enc, get_settings().settings_token_key) == "fresh-access"
    finally:
        set_settings(None)
        get_settings.cache_clear()


def test_http_graph_poll_ingests_and_reply_hits_graph():
    from app.mail.runtime import set_service

    http = FakeGraphHttp()
    graph = HttpGraphClient(token_provider=lambda: "tok", http=http)
    store = InMemoryEmailStore(seed=False)
    svc = EmailService(store=store, queue=InMemoryJobQueue(), graph=graph, local_mode=True)
    set_service(svc)
    try:
        account = store.ensure_account(USER, address="jane@contoso.com", demo=False)
        result = svc.refresh(USER)
        assert result["status"] == "ok"
        threads = store.list_threads(account.id)
        assert any("Staff Engineer" in (row.subject or "") for row in threads)
        thread = next(row for row in threads if "Staff Engineer" in (row.subject or ""))
        status, payload = svc.reply(USER, thread.id, {"bodyText": "Thanks Maya"})
        assert status == 201
        assert payload["deliveryStatus"] == "sent"
        assert any(call[0] == "POST" and str(call[1]).endswith("/sendMail") for call in http.calls)
        assert any(call[0] == "GET" and "messages/delta" in str(call[1]) for call in http.calls)
    finally:
        set_service(None)


def test_poll_all_creates_missing_subscription_when_graph_connected():
    store = InMemoryEmailStore(seed=False)
    settings_store = InMemorySettingsStore()
    now = utc_now()
    expires = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    settings_store.upsert_connection(
        USER,
        EmailConnection.model_validate(
            {
                "user_id": USER,
                "provider": "microsoft_365",
                "status": "expired",
                "account_email": "jane@contoso.com",
                "access_token_enc": "stale-access",
                "refresh_token_enc": "refresh-plain",
                "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                "created_at": now,
                "updated_at": now,
            }
        ),
        actor_id=USER,
    )
    graph = LocalGraphClient()
    svc = EmailService(
        store=store,
        queue=InMemoryJobQueue(),
        graph=graph,
        local_mode=True,
        settings_store=settings_store,
    )
    from app.settings.runtime import set_service as set_settings
    from app.settings.queues import InMemoryJobQueue as SettingsQueue
    from app.settings.service import SettingsService

    set_settings(SettingsService(store=settings_store, queue=SettingsQueue()))
    try:
        account = store.ensure_account(USER, address="jane@contoso.com", demo=False)
        assert store.get_subscription(account.id) is None
        svc.poll_all()
        saved = store.get_subscription(account.id)
        assert saved is not None
        linked = settings_store.list_connections(USER)[0]
        assert linked.webhook_subscription_id == saved.graph_subscription_id
        assert graph._subscriptions
    finally:
        set_settings(None)


def test_poll_all_renews_subscription_before_expiry():
    store = InMemoryEmailStore(seed=False)
    graph = LocalGraphClient()
    svc = EmailService(store=store, queue=InMemoryJobQueue(), graph=graph, local_mode=True)
    account = store.ensure_account(USER, address="jane@contoso.com", demo=False)
    soon = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    from app.mail.models import GraphSubscription

    store.upsert_subscription(
        GraphSubscription(
            email_account_id=account.id,
            graph_subscription_id="sub-old",
            resource="/me/messages",
            expires_at=soon,
            client_state="dev-mail-webhook",
            created_at=utc_now(),
        )
    )
    svc.poll_all()
    saved = store.get_subscription(account.id)
    assert saved is not None
    assert saved.graph_subscription_id == "sub-old"
    later = datetime.fromisoformat(saved.expires_at.replace("Z", "+00:00"))
    assert later - datetime.now(timezone.utc) > timedelta(hours=24)

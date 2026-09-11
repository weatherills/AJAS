"""Local Graph stand-in plus a Microsoft Graph client seam."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.mail.keys import hours_ago, new_id, utc_now


@dataclass
class GraphAttachment:
    name: str
    content_type: str
    size: int
    content: bytes = b""
    is_inline: bool = False
    content_id: str | None = None


@dataclass
class GraphMessage:
    id: str
    internet_message_id: str
    conversation_id: str
    subject: str
    from_address: str
    from_name: str
    to_addresses: list[str]
    body_text: str
    received_at: str
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    cc_addresses: list[str] = field(default_factory=list)
    body_html: str | None = None
    etag: str = "1"
    is_read: bool = False
    attachments: list[GraphAttachment] = field(default_factory=list)
    change_type: str = "created"


class GraphClient(Protocol):
    def fetch_message(self, account_id: str, graph_message_id: str) -> GraphMessage | None: ...

    def delta(self, account_id: str, token: str | None) -> tuple[list[GraphMessage], str]: ...

    def send_reply(
        self,
        account_id: str,
        *,
        conversation_id: str,
        internet_message_id: str,
        subject: str,
        body_text: str,
        to_addresses: list[str],
        attachments: list[GraphAttachment],
    ) -> GraphMessage: ...

    def create_subscription(
        self,
        *,
        notification_url: str,
        client_state: str,
        existing_id: str | None = None,
    ) -> dict: ...


class LocalGraphClient:
    """In-process mailbox used when Microsoft client id/secret are unset."""

    def __init__(self) -> None:
        self._messages: dict[str, dict[str, GraphMessage]] = {}
        self._pending: dict[str, list[GraphMessage]] = {}
        self._subscriptions: list[dict] = []

    def seed_pending(self, account_id: str, message: GraphMessage) -> None:
        self._pending.setdefault(account_id, []).append(message)
        self._messages.setdefault(account_id, {})[message.id] = message

    def put(self, account_id: str, message: GraphMessage) -> None:
        self._messages.setdefault(account_id, {})[message.id] = message

    def fetch_message(self, account_id: str, graph_message_id: str) -> GraphMessage | None:
        return self._messages.get(account_id, {}).get(graph_message_id)

    def delta(self, account_id: str, token: str | None) -> tuple[list[GraphMessage], str]:
        pending = self._pending.pop(account_id, [])
        return pending, token or utc_now()

    def send_reply(
        self,
        account_id: str,
        *,
        conversation_id: str,
        internet_message_id: str,
        subject: str,
        body_text: str,
        to_addresses: list[str],
        attachments: list[GraphAttachment],
    ) -> GraphMessage:
        sent = GraphMessage(
            id=f"graph-{new_id()}",
            internet_message_id=f"<sent-{new_id()}@ajas.dev>",
            conversation_id=conversation_id,
            subject=subject if subject.lower().startswith("re:") else f"Re: {subject}",
            from_address="local-user@ajas.dev",
            from_name="Local User",
            to_addresses=to_addresses,
            body_text=body_text,
            received_at=utc_now(),
            in_reply_to=internet_message_id,
            references=[internet_message_id],
            attachments=attachments,
            is_read=True,
        )
        self.put(account_id, sent)
        return sent

    def create_subscription(
        self,
        *,
        notification_url: str,
        client_state: str,
        existing_id: str | None = None,
    ) -> dict:
        from datetime import datetime, timedelta, timezone

        expires = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat().replace("+00:00", "Z")
        sub_id = existing_id or f"local-sub-{new_id()}"
        row = {
            "id": sub_id,
            "resource": "/me/messages",
            "expirationDateTime": expires,
            "notificationUrl": notification_url,
            "clientState": client_state,
        }
        self._subscriptions = [item for item in self._subscriptions if item.get("id") != sub_id]
        self._subscriptions.append(row)
        return row


class GraphHttp(Protocol):
    def request(self, method: str, url: str, *, headers: dict[str, str], body: dict | None = None) -> tuple[int, dict]: ...


class UrllibGraphHttp:
    def request(self, method: str, url: str, *, headers: dict[str, str], body: dict | None = None) -> tuple[int, dict]:
        import json
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        payload = json.dumps(body).encode("utf-8") if body is not None else None
        merged = {"Accept": "application/json", "User-Agent": "AJAS-mail/1.0", **headers}
        if payload is not None:
            merged["Content-Type"] = "application/json"
        req = Request(url, data=payload, method=method, headers=merged)
        try:
            with urlopen(req, timeout=20) as resp:
                raw = resp.read()
                parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                return int(getattr(resp, "status", 200)), parsed if isinstance(parsed, dict) else {"value": parsed}
        except HTTPError as exc:
            raw = exc.read() if hasattr(exc, "read") else b""
            try:
                parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            except Exception:
                parsed = {"error": raw.decode("utf-8", errors="replace")}
            if not isinstance(parsed, dict):
                parsed = {"error": parsed}
            return int(exc.code), parsed


class HttpGraphClient:
    """Microsoft Graph client used when OAuth client id/secret are configured."""

    def __init__(
        self,
        *,
        token_provider,
        http: GraphHttp | None = None,
        base_url: str = "https://graph.microsoft.com/v1.0",
    ) -> None:
        self._token_provider = token_provider
        self._http = http or UrllibGraphHttp()
        self._base = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        token = self._token_provider()
        return {"Authorization": f"Bearer {token}"}

    def _request(self, method: str, url: str, *, body: dict | None = None) -> tuple[int, dict]:
        status, payload = self._http.request(method, url, headers=self._headers(), body=body)
        if status == 401:
            status, payload = self._http.request(method, url, headers=self._headers(), body=body)
        return status, payload

    def fetch_message(self, account_id: str, graph_message_id: str) -> GraphMessage | None:
        status, payload = self._request(
            "GET",
            f"{self._base}/me/messages/{graph_message_id}?$expand=attachments",
        )
        if status == 404:
            return None
        if status >= 400:
            return None
        return _graph_message_from_json(payload)

    def delta(self, account_id: str, token: str | None) -> tuple[list[GraphMessage], str]:
        if token and str(token).startswith("http"):
            url = str(token)
        elif token:
            url = f"{self._base}/me/mailFolders/inbox/messages/delta?$deltatoken={token}"
        else:
            url = f"{self._base}/me/mailFolders/inbox/messages/delta"
        status, payload = self._request("GET", url)
        if status >= 400:
            return [], token or utc_now()
        rows = payload.get("value") or []
        messages = [_graph_message_from_json(item) for item in rows if isinstance(item, dict)]
        next_token = payload.get("@odata.deltaLink") or payload.get("@odata.nextLink") or token or utc_now()
        return messages, str(next_token)

    def send_reply(
        self,
        account_id: str,
        *,
        conversation_id: str,
        internet_message_id: str,
        subject: str,
        body_text: str,
        to_addresses: list[str],
        attachments: list[GraphAttachment],
    ) -> GraphMessage:
        import base64

        message: dict = {
            "subject": subject if subject.lower().startswith("re:") else f"Re: {subject}",
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in to_addresses],
        }
        if attachments:
            message["attachments"] = [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": item.name,
                    "contentType": item.content_type,
                    "contentBytes": base64.b64encode(item.content).decode("ascii") if item.content else "",
                }
                for item in attachments
            ]
        payload = {"message": message, "comment": body_text}
        self._request("POST", f"{self._base}/me/sendMail", body=payload)
        sent = GraphMessage(
            id=f"graph-{new_id()}",
            internet_message_id=f"<sent-{new_id()}@ajas.dev>",
            conversation_id=conversation_id,
            subject=payload["message"]["subject"],
            from_address="me",
            from_name="Me",
            to_addresses=to_addresses,
            body_text=body_text,
            received_at=utc_now(),
            in_reply_to=internet_message_id,
            attachments=attachments,
            is_read=True,
        )
        return sent

    def create_subscription(
        self,
        *,
        notification_url: str,
        client_state: str,
        existing_id: str | None = None,
    ) -> dict:
        from datetime import datetime, timedelta, timezone

        expires = (datetime.now(timezone.utc) + timedelta(hours=42)).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")
        if existing_id:
            status, payload = self._request(
                "PATCH",
                f"{self._base}/subscriptions/{existing_id}",
                body={"expirationDateTime": expires},
            )
            if status < 400:
                payload.setdefault("id", existing_id)
                payload.setdefault("resource", "/me/messages")
                payload.setdefault("expirationDateTime", expires)
                return payload
        status, payload = self._request(
            "POST",
            f"{self._base}/subscriptions",
            body={
                "changeType": "created,updated",
                "notificationUrl": notification_url,
                "resource": "/me/messages",
                "expirationDateTime": expires,
                "clientState": client_state,
            },
        )
        if status >= 400:
            raise RuntimeError(payload.get("error") or payload)
        payload.setdefault("expirationDateTime", expires)
        payload.setdefault("resource", "/me/messages")
        return payload


def _graph_message_from_json(payload: dict) -> GraphMessage:
    sender = ((payload.get("from") or {}).get("emailAddress") or {})
    to_rows = payload.get("toRecipients") or []
    attachments = []
    for item in payload.get("attachments") or []:
        if not isinstance(item, dict):
            continue
        raw = item.get("contentBytes") or ""
        content = b""
        if raw:
            import base64

            try:
                content = base64.b64decode(raw)
            except Exception:
                content = b""
        attachments.append(
            GraphAttachment(
                name=str(item.get("name") or "file"),
                content_type=str(item.get("contentType") or "application/octet-stream"),
                size=int(item.get("size") or len(content)),
                content=content,
                is_inline=bool(item.get("isInline")),
                content_id=item.get("contentId"),
            )
        )
    return GraphMessage(
        id=str(payload.get("id") or new_id()),
        internet_message_id=str(payload.get("internetMessageId") or f"<{new_id()}@graph>"),
        conversation_id=str(payload.get("conversationId") or payload.get("id") or new_id()),
        subject=str(payload.get("subject") or ""),
        from_address=str(sender.get("address") or ""),
        from_name=str(sender.get("name") or ""),
        to_addresses=[str((row.get("emailAddress") or {}).get("address") or "") for row in to_rows if isinstance(row, dict)],
        body_text=str((payload.get("body") or {}).get("content") or payload.get("bodyPreview") or ""),
        received_at=str(payload.get("receivedDateTime") or utc_now()),
        attachments=attachments,
        is_read=bool(payload.get("isRead")),
    )


def pending_followup(account_id: str, mailbox: str) -> GraphMessage:
    return GraphMessage(
        id=f"pending-{account_id[:8]}",
        internet_message_id=f"<pending-{account_id[:8]}@acme.test>",
        conversation_id=f"conv-pending-{account_id[:8]}",
        subject="Staff Engineer at Acme (JOB-SE-1) — next steps",
        from_address="maya@acme.test",
        from_name="Maya Chen",
        to_addresses=[mailbox],
        body_text="Could you share two times this week for a screen?",
        received_at=hours_ago(0.1),
    )


def _settings_access_token() -> str:
    from app.settings.runtime import try_get_service

    service = try_get_service()
    if service is None:
        raise RuntimeError("settings service is not available for Graph tokens")
    user_ids = []
    list_ids = getattr(service.store, "list_user_ids", None)
    if callable(list_ids):
        user_ids = list_ids()
    last_error: Exception | None = None
    for user_id in user_ids:
        try:
            return service.graph_access_token(user_id)
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError(str(last_error) if last_error else "no active Microsoft Graph token")


def default_graph_client() -> GraphClient:
    from app.config import get_settings, microsoft_oauth_configured

    settings = get_settings()
    if not microsoft_oauth_configured(settings):
        return LocalGraphClient()
    return HttpGraphClient(token_provider=_settings_access_token)

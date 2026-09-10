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


class LocalGraphClient:
    """In-process mailbox used when Microsoft client id/secret are unset."""

    def __init__(self) -> None:
        self._messages: dict[str, dict[str, GraphMessage]] = {}
        self._pending: dict[str, list[GraphMessage]] = {}

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


def default_graph_client() -> GraphClient:
    from app.config import get_settings, microsoft_oauth_configured

    settings = get_settings()
    if not microsoft_oauth_configured(settings):
        return LocalGraphClient()
    return LocalGraphClient()

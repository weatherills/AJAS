"""Gmail inbox + send beside Microsoft Graph. Flag-gated; mockable HTTP."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from app.flags import feature_enabled
from app.job_sources.keys import utc_now
from app.mail.intent import classify_email
from app.mail.graph import GraphMessage

GMAIL_FLAG = "gmail_adapter"
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
)


class GmailHttp(Protocol):
    def request(self, method: str, url: str, *, headers: dict[str, str], body: dict | None = None) -> tuple[int, dict]: ...


class UrllibGmailHttp:
    def request(self, method: str, url: str, *, headers: dict[str, str], body: dict | None = None) -> tuple[int, dict]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        payload = json.dumps(body).encode("utf-8") if body is not None else None
        merged = {"Accept": "application/json", "User-Agent": "AJAS-gmail/1.0", **headers}
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
            return int(exc.code), parsed if isinstance(parsed, dict) else {"error": parsed}


@dataclass
class GmailMessage:
    id: str
    thread_id: str
    subject: str
    from_address: str
    from_name: str
    to_addresses: list[str]
    body_text: str
    received_at: str
    label_ids: list[str] = field(default_factory=list)
    snippet: str = ""

    def to_graph(self) -> GraphMessage:
        return GraphMessage(
            id=self.id,
            internet_message_id=f"<{self.id}@gmail.ajas>",
            conversation_id=self.thread_id,
            subject=self.subject,
            from_address=self.from_address,
            from_name=self.from_name,
            to_addresses=self.to_addresses,
            body_text=self.body_text,
            received_at=self.received_at,
        )


class LocalGmailClient:
    """In-process Gmail stand-in used when OAuth is unset or in tests."""

    def __init__(self) -> None:
        self._messages: dict[str, list[GmailMessage]] = {}

    def seed(self, account_id: str, message: GmailMessage) -> None:
        self._messages.setdefault(account_id, []).append(message)

    def list_messages(self, account_id: str, *, labels: list[str] | None = None) -> list[GmailMessage]:
        rows = list(self._messages.get(account_id) or [])
        if labels:
            wanted = {item.lower() for item in labels}
            rows = [row for row in rows if wanted & {lab.lower() for lab in row.label_ids} or "INBOX" in wanted]
        return rows

    def get_message(self, account_id: str, message_id: str) -> GmailMessage | None:
        for row in self._messages.get(account_id) or []:
            if row.id == message_id:
                return row
        return None

    def send(
        self,
        account_id: str,
        *,
        to_addresses: list[str],
        subject: str,
        body_text: str,
        thread_id: str | None = None,
    ) -> GmailMessage:
        sent = GmailMessage(
            id=f"gmail-{uuid4().hex[:10]}",
            thread_id=thread_id or f"thread-{uuid4().hex[:8]}",
            subject=subject if subject.lower().startswith("re:") else f"Re: {subject}",
            from_address="me@ajas.dev",
            from_name="AJAS",
            to_addresses=to_addresses,
            body_text=body_text,
            received_at=utc_now(),
            label_ids=["SENT"],
        )
        self.seed(account_id, sent)
        return sent


def parse_thread(messages: list[GmailMessage]) -> dict[str, Any]:
    ordered = list(messages)
    latest = ordered[-1] if ordered else None
    intent = classify_email(subject=latest.subject if latest else "", body=latest.body_text if latest else "")
    return {
        "threadId": latest.thread_id if latest else None,
        "count": len(ordered),
        "subject": latest.subject if latest else "",
        "from": latest.from_address if latest else "",
        "intent": intent["intent"],
        "confidence": intent["confidence"],
        "snippet": (latest.body_text if latest else "")[:280],
        "messages": [
            {
                "id": item.id,
                "from": item.from_address,
                "subject": item.subject,
                "receivedAt": item.received_at,
            }
            for item in ordered
        ],
    }


def oauth_configured(client_id: str = "", client_secret: str = "") -> bool:
    return bool((client_id or "").strip() and (client_secret or "").strip())


def sync_inbox(
    account_id: str,
    *,
    labels: list[str] | None = None,
    client: LocalGmailClient | None = None,
    fixtures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not feature_enabled(GMAIL_FLAG):
        return {"enabled": False, "items": [], "threads": [], "reason": "flag_off"}
    mailbox = client or LocalGmailClient()
    if fixtures:
        for row in fixtures:
            mailbox.seed(
                account_id,
                GmailMessage(
                    id=str(row.get("id") or uuid4()),
                    thread_id=str(row.get("threadId") or row.get("thread_id") or "thread-1"),
                    subject=str(row.get("subject") or ""),
                    from_address=str(row.get("from") or row.get("from_address") or ""),
                    from_name=str(row.get("fromName") or ""),
                    to_addresses=list(row.get("to") or row.get("to_addresses") or []),
                    body_text=str(row.get("body") or row.get("body_text") or ""),
                    received_at=str(row.get("receivedAt") or utc_now()),
                    label_ids=list(row.get("labelIds") or row.get("labels") or ["INBOX"]),
                ),
            )
    items = mailbox.list_messages(account_id, labels=labels or ["INBOX"])
    grouped: dict[str, list[GmailMessage]] = {}
    for item in items:
        grouped.setdefault(item.thread_id, []).append(item)
    threads = [parse_thread(group) for group in grouped.values()]
    return {
        "enabled": True,
        "reason": "ok",
        "items": [
            {
                "id": item.id,
                "threadId": item.thread_id,
                "subject": item.subject,
                "from": item.from_address,
                "snippet": item.body_text[:180],
                "labels": item.label_ids,
            }
            for item in items
        ],
        "threads": threads,
        "scopes": list(GMAIL_SCOPES),
    }


def send_mail(
    account_id: str,
    *,
    to_addresses: list[str],
    subject: str,
    body_text: str,
    thread_id: str | None = None,
    client: LocalGmailClient | None = None,
) -> dict[str, Any]:
    if not feature_enabled(GMAIL_FLAG):
        return {"enabled": False, "reason": "flag_off"}
    mailbox = client or LocalGmailClient()
    sent = mailbox.send(account_id, to_addresses=to_addresses, subject=subject, body_text=body_text, thread_id=thread_id)
    return {
        "enabled": True,
        "reason": "ok",
        "id": sent.id,
        "threadId": sent.thread_id,
        "subject": sent.subject,
        "to": sent.to_addresses,
    }


def rfc822_raw(*, to_addresses: list[str], subject: str, body_text: str) -> str:
    to = ", ".join(to_addresses)
    return base64.urlsafe_b64encode(f"To: {to}\r\nSubject: {subject}\r\n\r\n{body_text}".encode("utf-8")).decode("ascii")

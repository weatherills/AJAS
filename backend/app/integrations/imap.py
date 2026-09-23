"""IMAP inbox + SMTP send beside Microsoft Graph. Flag-gated; fixture-first.

Live imaplib/smtplib is opt-in (IMAP_LIVE + SSL + allowlisted host + credentials).
Tests and default ingest use LocalImapClient plus operator-supplied RFC822/JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from app.config import get_settings
from app.flags import feature_enabled
from app.integrations.imap_spec import RATE_PLAN, map_imap_message, parse_rfc822, unwrap_imap_payload
from app.job_sources.keys import utc_now
from app.mail.graph import GraphMessage
from app.mail.imap_labels import map_label, map_labels
from app.mail.intent import classify_email

IMAP_FLAG = "imap_transport"
_SESSION: dict[str, str] = {}
_LIVE_TRANSPORT: dict[str, Any] = {}


class ImapClient(Protocol):
    def seed(self, account_id: str, message: "ImapMessage") -> None: ...

    def list_messages(self, account_id: str, *, folder: str | None = None, since_uid: str | None = None) -> list["ImapMessage"]: ...

    def send(
        self,
        account_id: str,
        *,
        to_addresses: list[str],
        subject: str,
        body_text: str,
        thread_id: str | None = None,
        folder: str = "Sent",
    ) -> "ImapMessage": ...


@dataclass
class ImapMessage:
    uid: str
    message_id: str
    thread_id: str
    subject: str
    from_address: str
    from_name: str
    to_addresses: list[str]
    body_text: str
    received_at: str
    folder: str = "INBOX"
    flags: list[str] = field(default_factory=list)
    in_reply_to: str | None = None
    snippet: str = ""

    def to_graph(self) -> GraphMessage:
        return GraphMessage(
            id=self.uid,
            internet_message_id=self.message_id or f"<{self.uid}@imap.ajas>",
            conversation_id=self.thread_id,
            subject=self.subject,
            from_address=self.from_address,
            from_name=self.from_name,
            to_addresses=self.to_addresses,
            body_text=self.body_text,
            received_at=self.received_at,
            in_reply_to=self.in_reply_to,
        )


class LocalImapClient:
    """In-process IMAP/SMTP stand-in used by tests and fixture ingest."""

    def __init__(self) -> None:
        self._messages: dict[str, list[ImapMessage]] = {}
        self._uid: dict[str, int] = {}

    def seed(self, account_id: str, message: ImapMessage) -> None:
        self._messages.setdefault(account_id, []).append(message)
        try:
            uid_n = int(message.uid)
        except (TypeError, ValueError):
            uid_n = 0
        self._uid[account_id] = max(self._uid.get(account_id, 0), uid_n)

    def list_messages(self, account_id: str, *, folder: str | None = None, since_uid: str | None = None) -> list[ImapMessage]:
        rows = list(self._messages.get(account_id) or [])
        if folder:
            wanted = folder.lower()
            rows = [row for row in rows if row.folder.lower() == wanted or wanted in {flag.lower() for flag in row.flags}]
        if since_uid:
            try:
                floor = int(since_uid)
                rows = [row for row in rows if _uid_int(row.uid) > floor]
            except (TypeError, ValueError):
                pass
        return rows

    def send(
        self,
        account_id: str,
        *,
        to_addresses: list[str],
        subject: str,
        body_text: str,
        thread_id: str | None = None,
        folder: str = "Sent",
    ) -> ImapMessage:
        nxt = self._uid.get(account_id, 0) + 1
        sent = ImapMessage(
            uid=str(nxt),
            message_id=f"<sent-{uuid4().hex[:10]}@ajas.dev>",
            thread_id=thread_id or f"thread-{uuid4().hex[:8]}",
            subject=subject if subject.lower().startswith("re:") else f"Re: {subject}",
            from_address="me@ajas.dev",
            from_name="AJAS",
            to_addresses=to_addresses,
            body_text=body_text,
            received_at=utc_now(),
            folder=folder,
            flags=["\\Seen", "\\Sent"],
            snippet=body_text[:180],
        )
        self.seed(account_id, sent)
        return sent


def _uid_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def remember_credentials(*, host: str = "", username: str = "", password: str = "") -> None:
    if host.strip():
        _SESSION["host"] = host.strip()
    if username.strip():
        _SESSION["username"] = username.strip()
    if password.strip():
        _SESSION["password"] = password.strip()


def clear_credentials() -> None:
    _SESSION.clear()


class LiveImapError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def set_live_transport(*, fetch: Any = None, send: Any = None) -> None:
    """Tests inject fetch/send callables so imaplib/smtplib never open sockets."""
    _LIVE_TRANSPORT.clear()
    if fetch is not None:
        _LIVE_TRANSPORT["fetch"] = fetch
    if send is not None:
        _LIVE_TRANSPORT["send"] = send


def clear_live_transport() -> None:
    _LIVE_TRANSPORT.clear()


def _settings_cred(name: str) -> str:
    if _SESSION.get(name):
        return _SESSION[name]
    settings = get_settings()
    return str(getattr(settings, f"imap_{name}", "") or "").strip()


def credentials_present() -> bool:
    settings = get_settings()
    host = _SESSION.get("host") or str(getattr(settings, "imap_host", "") or "").strip()
    user = _settings_cred("username")
    password = _settings_cred("password")
    return bool(host and user and password)


def smtp_configured() -> bool:
    settings = get_settings()
    host = str(getattr(settings, "smtp_host", "") or getattr(settings, "imap_host", "") or "").strip()
    return bool(host and credentials_present())


def allowed_hosts() -> frozenset[str]:
    settings = get_settings()
    raw = str(getattr(settings, "imap_allowed_hosts", "") or "").strip()
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def live_fetch_allowed() -> bool:
    settings = get_settings()
    if not bool(getattr(settings, "imap_live", False)):
        return False
    if not bool(getattr(settings, "imap_use_ssl", True)):
        return False
    if not credentials_present():
        return False
    host = (_SESSION.get("host") or str(getattr(settings, "imap_host", "") or "")).strip().lower()
    allow = allowed_hosts()
    return bool(host and allow and host in allow)


def live_connect_guard() -> dict[str, Any]:
    """Fail closed before opening a socket."""
    if not feature_enabled(IMAP_FLAG):
        return {"ok": False, "reason": "flag_off", "bypass": False}
    if not live_fetch_allowed():
        if not credentials_present():
            return {"ok": False, "reason": "needs_auth", "bypass": False}
        return {"ok": False, "reason": "live_disabled", "bypass": False}
    return {"ok": True, "reason": "ok", "bypass": False}


def _resolved_host() -> str:
    settings = get_settings()
    return (_SESSION.get("host") or str(getattr(settings, "imap_host", "") or "")).strip()


def fetch_via_imaplib(*, folder: str = "INBOX", since_uid: str | None = None) -> list[ImapMessage]:
    """IMAP4_SSL UID SEARCH + RFC822 FETCH. Host comes from env/session allowlist only."""
    gate = live_connect_guard()
    if not gate["ok"]:
        raise LiveImapError(str(gate["reason"]))
    injected = _LIVE_TRANSPORT.get("fetch")
    if injected is not None:
        return list(injected(folder=folder, since_uid=since_uid) or [])
    import imaplib
    import ssl

    settings = get_settings()
    host = _resolved_host()
    port = int(getattr(settings, "imap_port", 993) or 993)
    user = _settings_cred("username")
    password = _settings_cred("password")
    mailbox = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context())
    try:
        mailbox.login(user, password)
        mailbox.select(folder or "INBOX")
        criterion = f"UID {_uid_int(since_uid or '0') + 1}:*" if since_uid else "ALL"
        _, data = mailbox.uid("SEARCH", None, criterion)
        uids = (data[0] or b"").split() if data else []
        rows: list[ImapMessage] = []
        for uid in uids:
            _, fetched = mailbox.uid("FETCH", uid, "(RFC822)")
            raw = b""
            if fetched and fetched[0] and isinstance(fetched[0], tuple) and len(fetched[0]) > 1:
                raw = fetched[0][1] if isinstance(fetched[0][1], (bytes, str)) else b""
            uid_s = uid.decode("ascii") if isinstance(uid, bytes) else str(uid)
            parsed = parse_rfc822(raw) if raw else {}
            parsed["uid"] = uid_s
            parsed["folder"] = folder or "INBOX"
            rows.append(_message_from_mapped(map_imap_message(parsed)))
        return rows
    finally:
        try:
            mailbox.logout()
        except Exception:
            pass


def send_via_smtplib(
    *,
    to_addresses: list[str],
    subject: str,
    body_text: str,
    thread_id: str | None = None,
) -> ImapMessage:
    """SMTP_SSL send. Host comes from env/session allowlist only."""
    gate = live_connect_guard()
    if not gate["ok"]:
        raise LiveImapError(str(gate["reason"]))
    injected = _LIVE_TRANSPORT.get("send")
    if injected is not None:
        return injected(to_addresses=to_addresses, subject=subject, body_text=body_text, thread_id=thread_id)
    import smtplib
    import ssl
    from email.message import EmailMessage

    settings = get_settings()
    host = str(getattr(settings, "smtp_host", "") or _resolved_host()).strip()
    port = int(getattr(settings, "smtp_port", 465) or 465)
    user = _settings_cred("username")
    password = _settings_cred("password")
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = ", ".join(to_addresses)
    msg["Subject"] = subject
    if thread_id:
        msg["In-Reply-To"] = thread_id
    msg.set_content(body_text)
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    return ImapMessage(
        uid="0",
        message_id=str(msg.get("Message-ID") or f"<sent-{uuid4().hex[:10]}@ajas.dev>"),
        thread_id=thread_id or f"thread-{uuid4().hex[:8]}",
        subject=subject if subject.lower().startswith("re:") else f"Re: {subject}",
        from_address=user,
        from_name="AJAS",
        to_addresses=to_addresses,
        body_text=body_text,
        received_at=utc_now(),
        folder="Sent",
        flags=["\\Seen", "\\Sent"],
        snippet=body_text[:180],
    )


def _message_from_mapped(mapped: dict[str, Any]) -> ImapMessage:
    uid = str(mapped.get("sourceMessageId") or uuid4().hex[:10])
    to_addrs = list(mapped.get("toAddresses") or [])
    if not to_addrs and mapped.get("to"):
        to_addrs = [part.strip() for part in str(mapped["to"]).split(",") if part.strip()]
    body = str(mapped.get("body") or "")
    folder = str(mapped.get("folder") or "INBOX")
    return ImapMessage(
        uid=uid,
        message_id=str(mapped.get("internetMessageId") or f"<{uid}@imap.ajas>"),
        thread_id=str(mapped.get("threadId") or uid),
        subject=str(mapped.get("subject") or ""),
        from_address=str(mapped.get("from") or ""),
        from_name=str(mapped.get("fromName") or ""),
        to_addresses=to_addrs,
        body_text=body,
        received_at=str(mapped.get("receivedAt") or utc_now()),
        folder=folder,
        flags=[folder],
        snippet=body[:180],
    )


def _seed_payload(account_id: str, mailbox: LocalImapClient, payload: Any) -> None:
    unwrapped = unwrap_imap_payload(payload)
    rows: list[Any] = []
    if isinstance(unwrapped, dict) and isinstance(unwrapped.get("pages"), list):
        for page in unwrapped["pages"]:
            if isinstance(page, dict):
                rows.extend(page.get("messages") or page.get("jobs") or [])
    elif isinstance(unwrapped, dict):
        rows = list(unwrapped.get("messages") or unwrapped.get("jobs") or [])
    for row in rows:
        if not isinstance(row, dict):
            continue
        mailbox.seed(account_id, _message_from_mapped(map_imap_message(row)))


def parse_thread(messages: list[ImapMessage]) -> dict[str, Any]:
    ordered = list(messages)
    latest = ordered[-1] if ordered else None
    intent = classify_email(subject=latest.subject if latest else "", body=latest.body_text if latest else "")
    labels = [item.folder for item in ordered]
    mapped = map_labels(labels)
    return {
        "threadId": latest.thread_id if latest else None,
        "count": len(ordered),
        "subject": latest.subject if latest else "",
        "from": latest.from_address if latest else "",
        "intent": intent["intent"],
        "confidence": intent["confidence"],
        "state": mapped["current"],
        "snippet": (latest.body_text if latest else "")[:280],
        "messages": [
            {
                "id": item.uid,
                "from": item.from_address,
                "subject": item.subject,
                "folder": item.folder,
                "receivedAt": item.received_at,
            }
            for item in ordered
        ],
    }


def sync_inbox(
    account_id: str,
    *,
    folder: str | None = None,
    since_uid: str | None = None,
    client: LocalImapClient | None = None,
    fixtures: list[dict[str, Any]] | None = None,
    payload: Any = None,
    live: bool = False,
) -> dict[str, Any]:
    if not feature_enabled(IMAP_FLAG):
        return {"enabled": False, "items": [], "threads": [], "reason": "flag_off"}
    if live:
        gate = live_connect_guard()
        if not gate["ok"]:
            return {"enabled": True, "items": [], "threads": [], "reason": gate["reason"], "bypass": False}
        try:
            live_rows = fetch_via_imaplib(folder=folder or "INBOX", since_uid=since_uid)
        except LiveImapError as exc:
            return {"enabled": True, "items": [], "threads": [], "reason": exc.reason, "bypass": False}
        mailbox = client or LocalImapClient()
        for row in live_rows:
            mailbox.seed(account_id, row)
        items = mailbox.list_messages(account_id, folder=folder, since_uid=since_uid)
        grouped: dict[str, list[ImapMessage]] = {}
        for item in items:
            grouped.setdefault(item.thread_id, []).append(item)
        cap = int(RATE_PLAN["ingest"]["capPerWindow"])
        items = items[:cap]
        uids = [_uid_int(item.uid) for item in items]
        return {
            "enabled": True,
            "reason": "ok",
            "liveFetch": True,
            "folder": folder or "INBOX",
            "cursor": str(max(uids)) if uids else since_uid or "0",
            "items": [
                {
                    "id": item.uid,
                    "threadId": item.thread_id,
                    "subject": item.subject,
                    "from": item.from_address,
                    "snippet": item.snippet or item.body_text[:180],
                    "folder": item.folder,
                    "state": map_label(item.folder),
                    "internetMessageId": item.message_id,
                }
                for item in items
            ],
            "threads": [parse_thread(group) for group in grouped.values()],
        }
    mailbox = client or LocalImapClient()
    if fixtures:
        _seed_payload(account_id, mailbox, {"messages": fixtures})
    if payload is not None:
        _seed_payload(account_id, mailbox, payload)
    items = mailbox.list_messages(account_id, folder=folder, since_uid=since_uid)
    grouped: dict[str, list[ImapMessage]] = {}
    for item in items:
        grouped.setdefault(item.thread_id, []).append(item)
    cap = int(RATE_PLAN["ingest"]["capPerWindow"])
    items = items[:cap]
    uids = [_uid_int(item.uid) for item in items]
    return {
        "enabled": True,
        "reason": "ok",
        "liveFetch": False,
        "folder": folder or "INBOX",
        "cursor": str(max(uids)) if uids else since_uid or "0",
        "items": [
            {
                "id": item.uid,
                "threadId": item.thread_id,
                "subject": item.subject,
                "from": item.from_address,
                "snippet": item.snippet or item.body_text[:180],
                "folder": item.folder,
                "state": map_label(item.folder),
                "internetMessageId": item.message_id,
            }
            for item in items
        ],
        "threads": [parse_thread(group) for group in grouped.values()],
    }


def send_mail(
    account_id: str,
    *,
    to_addresses: list[str],
    subject: str,
    body_text: str,
    thread_id: str | None = None,
    client: LocalImapClient | None = None,
    live: bool = False,
) -> dict[str, Any]:
    if not feature_enabled(IMAP_FLAG):
        return {"enabled": False, "reason": "flag_off"}
    if live:
        gate = live_connect_guard()
        if not gate["ok"]:
            return {"enabled": True, "reason": gate["reason"], "bypass": False}
        try:
            sent = send_via_smtplib(
                to_addresses=to_addresses,
                subject=subject,
                body_text=body_text,
                thread_id=thread_id,
            )
        except LiveImapError as exc:
            return {"enabled": True, "reason": exc.reason, "bypass": False}
        mailbox = client or LocalImapClient()
        mailbox.seed(account_id, sent)
        return {
            "enabled": True,
            "reason": "ok",
            "liveFetch": True,
            "id": sent.uid,
            "threadId": sent.thread_id,
            "subject": sent.subject,
            "to": sent.to_addresses,
            "folder": sent.folder,
            "state": map_label(sent.folder),
        }
    mailbox = client or LocalImapClient()
    sent = mailbox.send(
        account_id,
        to_addresses=to_addresses,
        subject=subject,
        body_text=body_text,
        thread_id=thread_id,
    )
    return {
        "enabled": True,
        "reason": "ok",
        "id": sent.uid,
        "threadId": sent.thread_id,
        "subject": sent.subject,
        "to": sent.to_addresses,
        "folder": sent.folder,
        "state": map_label(sent.folder),
    }


def rfc822_fixture(*, uid: str, subject: str, from_address: str, to_address: str, body: str) -> str:
    return (
        f"From: {from_address}\r\n"
        f"To: {to_address}\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: <{uid}@imap.ajas>\r\n"
        f"Date: Sun, 01 Mar 2026 12:00:00 +0000\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        f"{body}\r\n"
    )

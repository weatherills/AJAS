"""IMAP/SMTP ingest executable contract (source of truth).

Microsoft Graph remains the Email PRD transport. This connector adds IMAP FETCH
plus SMTP send for operator-supplied RFC822/envelope fixtures. Live imaplib
connections require ``IMAP_LIVE``, SSL, credentials, and an allowlisted host.
``SOURCE_TYPES`` stays {greenhouse, lever}.
"""

from __future__ import annotations

from email import policy
from email.parser import BytesParser, Parser
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from app.integrations.linkedin_spec import PAGINATION, RATE_PLAN as LINKEDIN_RATE_PLAN
from app.integrations.listing_fields import extract_mapped_field, nested_text, strip_pii
from app.job_sources.circuit import FAILURE_THRESHOLD, OPEN_SECONDS
from app.job_sources.keys import utc_now
from app.mail.imap_labels import map_label

FIELD_MAP: tuple[dict[str, Any], ...] = (
    {
        "imap": "uid",
        "aliases": ("id", "message_id", "messageId", "internetMessageId"),
        "internal": "sourceMessageId",
        "type": "string",
        "nullable": False,
        "fallback": "canonical_id[:12]",
    },
    {
        "imap": "message_id",
        "aliases": ("messageId", "internetMessageId", "Message-ID"),
        "internal": "internetMessageId",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "imap": "thread_id",
        "aliases": ("threadId", "conversationId", "in_reply_to", "inReplyTo"),
        "internal": "threadId",
        "type": "string",
        "nullable": False,
        "fallback": "",
    },
    {
        "imap": "subject",
        "aliases": ("Subject",),
        "internal": "subject",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "imap": "from",
        "aliases": ("from_address", "fromAddress", "sender"),
        "internal": "from",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "imap": "to",
        "aliases": ("to_addresses", "toAddresses",),
        "internal": "to",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "imap": "body",
        "aliases": ("body_text", "bodyText", "text", "snippet"),
        "internal": "body",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "imap": "date",
        "aliases": ("receivedAt", "received_at", "internalDate"),
        "internal": "receivedAt",
        "type": "datetime",
        "nullable": True,
        "fallback": "",
    },
    {
        "imap": "folder",
        "aliases": ("mailbox", "label", "labels"),
        "internal": "folder",
        "type": "string",
        "nullable": True,
        "fallback": "INBOX",
    },
)

API_CONTRACT: dict[str, Any] = {
    "publicSearchApi": False,
    "emailPrdTransport": "microsoft-graph",
    "imapFetch": "uid-search-rfc822",
    "smtpSend": "starttls-or-ssl",
    "liveFetch": "opt-in-allowlisted-ssl",
    "acceptedFeeds": (
        "ajas_fixture_json",
        "imap_rfc822",
        "imap_fetch_envelope",
    ),
    "notes": (
        "Graph remains the Email PRD mailbox. IMAP/SMTP is a flag-gated extra connector. "
        "AJAS ingests operator-supplied RFC822 and FETCH envelopes. Live imaplib is off "
        "unless IMAP_LIVE is set, TLS is on, credentials exist, and the host is allowlisted."
    ),
    "docs": (
        "https://datatracker.ietf.org/doc/html/rfc3501",
        "https://datatracker.ietf.org/doc/html/rfc5322",
        "https://datatracker.ietf.org/doc/html/rfc8314",
    ),
}

RATE_PLAN: dict[str, dict[str, Any]] = {
    "ingest": {
        **LINKEDIN_RATE_PLAN["ingest"],
        "capPerWindow": 20,
        "windowSeconds": 60,
        "circuitFailureThreshold": FAILURE_THRESHOLD,
        "circuitOpenSeconds": OPEN_SECONDS,
        "retryStatus": (429, 408, 421, 450, 503, 504),
    }
}

SECURITY_CHECKLIST: tuple[dict[str, Any], ...] = (
    {
        "id": "no_unsolicited_live_fetch",
        "rule": "Do not open IMAP/SMTP sockets unless IMAP_LIVE, SSL, credentials, and host allowlist all pass.",
    },
    {
        "id": "credentials",
        "rule": "IMAP_USERNAME/IMAP_PASSWORD never appear in health, spec, or logs. Missing live creds fail closed.",
    },
    {
        "id": "pii_minimization",
        "rule": "Do not log message bodies. Store FIELD_MAP listing fields only.",
    },
    {
        "id": "access_control",
        "rule": "HTTP routes require JWT; Graph stays the Email PRD transport; SOURCE_TYPES stays greenhouse|lever.",
    },
)


def _addresses(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.extend(addr for _, addr in getaddresses([item]) if addr)
            elif isinstance(item, dict):
                addr = nested_text(item.get("address") or item.get("email") or item.get("mailbox"))
                if addr:
                    out.append(addr)
        return out
    if isinstance(value, str) and value.strip():
        return [addr for _, addr in getaddresses([value]) if addr]
    if isinstance(value, dict):
        addr = nested_text(value.get("address") or value.get("email") or value.get("mailbox"))
        return [addr] if addr else []
    return []


def _first_address(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        name = nested_text(value.get("name") or value.get("displayName"))
        addr = nested_text(value.get("address") or value.get("email") or value.get("mailbox"))
        return name, addr
    if isinstance(value, str) and value.strip():
        parsed = getaddresses([value])
        if parsed:
            return parsed[0][0] or "", parsed[0][1] or value.strip()
    if isinstance(value, list) and value:
        return _first_address(value[0])
    return "", ""


def _parse_date(value: Any) -> str:
    text = nested_text(value)
    if not text:
        return ""
    try:
        stamp = parsedate_to_datetime(text)
        return stamp.astimezone().isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError):
        return text


def parse_rfc822(raw: str | bytes) -> dict[str, Any]:
    """Parse an RFC822 message. Body is kept; extra email headers are not logged."""
    if isinstance(raw, bytes):
        message = BytesParser(policy=policy.default).parsebytes(raw)
    else:
        message = Parser(policy=policy.default).parsestr(str(raw))
    from_name, from_addr = _first_address(str(message.get("from") or ""))
    body = ""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_content()
                if isinstance(payload, str):
                    body = payload
                    break
    else:
        payload = message.get_content()
        body = payload if isinstance(payload, str) else ""
    refs = str(message.get("references") or "").split()
    in_reply = str(message.get("in-reply-to") or "").strip()
    msg_id = str(message.get("message-id") or "").strip()
    return strip_pii(
        {
            "uid": msg_id or nested_text(message.get("subject")),
            "message_id": msg_id,
            "thread_id": in_reply or (refs[0] if refs else msg_id),
            "subject": str(message.get("subject") or ""),
            "from": from_addr,
            "from_name": from_name,
            "to": _addresses(str(message.get("to") or "")),
            "cc": _addresses(str(message.get("cc") or "")),
            "date": _parse_date(message.get("date")),
            "body": body.strip(),
            "in_reply_to": in_reply,
            "references": refs,
            "folder": "INBOX",
        }
    )


def flatten_imap_message(job: dict[str, Any], *, folder: str = "INBOX") -> dict[str, Any]:
    row = strip_pii(dict(job))
    envelope = job.get("envelope") if isinstance(job.get("envelope"), dict) else None
    if envelope:
        row = {**strip_pii(dict(envelope)), **{k: v for k, v in row.items() if k != "envelope"}}
        job = {**envelope, **job}
    rfc = job.get("rfc822") or job.get("raw") or job.get("source")
    if isinstance(rfc, (str, bytes)) and (str(rfc).lstrip().lower().startswith("from:") or b"Message-ID:" in (rfc if isinstance(rfc, bytes) else rfc.encode("utf-8", errors="replace"))):
        parsed = parse_rfc822(rfc)
        row = {**parsed, **{k: v for k, v in row.items() if nested_text(v)}}
    name, addr = _first_address(job.get("from") or job.get("from_address") or job.get("sender"))
    if addr:
        row["from"] = addr
        row["from_name"] = name or nested_text(row.get("from_name"))
    tos = _addresses(job.get("to") or job.get("to_addresses") or job.get("toAddresses") or row.get("to"))
    if tos:
        row["to"] = tos
        row["to_addresses"] = tos
    if not nested_text(row.get("folder")):
        labels = job.get("labels") or job.get("flags")
        if isinstance(labels, list) and labels:
            row["folder"] = nested_text(labels[0]) or folder
        else:
            row["folder"] = nested_text(job.get("folder") or job.get("mailbox")) or folder
    if not nested_text(row.get("date")):
        row["date"] = _parse_date(job.get("receivedAt") or job.get("received_at") or job.get("internalDate"))
    uid = nested_text(row.get("uid") or row.get("id") or row.get("message_id"))
    row["uid"] = uid
    row["id"] = uid
    msg_id = nested_text(row.get("message_id") or row.get("internetMessageId")) or (f"<{uid}@imap.ajas>" if uid else "")
    row["message_id"] = msg_id
    in_reply = nested_text(row.get("in_reply_to") or row.get("inReplyTo"))
    refs = row.get("references") if isinstance(row.get("references"), list) else str(row.get("references") or "").split()
    thread = nested_text(row.get("thread_id") or row.get("threadId") or row.get("conversationId"))
    row["thread_id"] = thread or in_reply or (refs[0] if refs else msg_id or uid)
    row["in_reply_to"] = in_reply
    row["references"] = [item for item in refs if item]
    row["state"] = map_label(str(row.get("folder") or "INBOX"))
    if isinstance(row.get("to"), list):
        row["to"] = ", ".join(row["to"])
    return strip_pii(row)


def unwrap_imap_payload(payload: Any) -> Any:
    """Normalize RFC822, FETCH envelopes, and AJAS cursor pages."""
    if isinstance(payload, (bytes, str)):
        text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
        if "Message-ID:" in text or text.lstrip().lower().startswith("from:"):
            return {"messages": [flatten_imap_message(parse_rfc822(payload))], "nextUid": None}
        return payload
    if not isinstance(payload, dict):
        return payload
    if not any(key in payload for key in ("messages", "items", "pages")) and (
        payload.get("envelope")
        or payload.get("rfc822")
        or payload.get("raw")
        or payload.get("uid")
        or payload.get("from")
        or payload.get("subject")
    ):
        return {"messages": [flatten_imap_message(payload)], "nextUid": None}
    rows = payload.get("messages")
    if not isinstance(rows, list):
        rows = payload.get("items") if isinstance(payload.get("items"), list) else None
    if isinstance(rows, list):
        jobs = [flatten_imap_message(row) if isinstance(row, dict) else row for row in rows]
        nxt = payload.get("nextUid") or payload.get("nextCursor")
        uids = [int(row["uid"]) for row in jobs if isinstance(row, dict) and str(row.get("uid") or "").isdigit()]
        cursor = payload.get("cursor") or payload.get("uid") or (str(min(uids)) if uids else "0")
        return {**payload, "cursor": str(cursor), "messages": jobs, "jobs": jobs, "nextCursor": str(nxt) if nxt else None}
    if isinstance(payload.get("pages"), list):
        pages = []
        for page in payload["pages"]:
            if not isinstance(page, dict):
                pages.append(page)
                continue
            rows = page.get("messages") if isinstance(page.get("messages"), list) else page.get("jobs")
            if isinstance(rows, list):
                pages.append(
                    {
                        **page,
                        "jobs": [flatten_imap_message(row) if isinstance(row, dict) else row for row in rows],
                        "messages": [flatten_imap_message(row) if isinstance(row, dict) else row for row in rows],
                    }
                )
            else:
                pages.append(page)
        return {**payload, "pages": pages}
    return payload


def map_imap_message(job: dict[str, Any]) -> dict[str, Any]:
    flat = flatten_imap_message(job)
    mapped = {row["internal"]: extract_mapped_field(flat, row, source_key="imap") for row in FIELD_MAP}
    mapped["fromName"] = nested_text(flat.get("from_name"))
    mapped["state"] = map_label(mapped.get("folder") or "INBOX")
    mapped["internetMessageId"] = mapped.get("internetMessageId") or nested_text(flat.get("message_id"))
    mapped["threadId"] = mapped.get("threadId") or mapped.get("internetMessageId") or mapped.get("sourceMessageId")
    mapped["toAddresses"] = _addresses(flat.get("to_addresses") or flat.get("to"))
    if not mapped.get("receivedAt"):
        mapped["receivedAt"] = utc_now()
    if not mapped.get("folder"):
        mapped["folder"] = "INBOX"
    return mapped


def spec_bundle() -> dict[str, Any]:
    return {
        "source": "imap",
        "generatedAt": utc_now(),
        "flag": "imap_transport",
        "liveScrape": False,
        "sourceTypesUnchanged": True,
        "api": API_CONTRACT,
        "fieldMap": [dict(row) for row in FIELD_MAP],
        "ratePlan": RATE_PLAN,
        "pagination": {**PAGINATION, "mode": "uid"},
        "security": [dict(row) for row in SECURITY_CHECKLIST],
        "http": {
            "sync": "POST /api/v1/integrations/imap/sync",
            "send": "POST /api/v1/integrations/imap/send",
            "spec": "GET /api/v1/integrations/imap/spec",
        },
    }

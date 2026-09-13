"""Email provider v2, classification, calendar, digests, web push, bounce, SPF."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from uuid import uuid4

from app.matching.keys import utc_now

LABELS = ("offer", "interview", "nurture", "reject", "followup", "other")
_CONNECTIONS: dict[str, dict[str, Any]] = {}
_PUSH: dict[str, dict[str, Any]] = {}
_BOUNCES: dict[str, dict[str, Any]] = {}
_SUPPRESS: set[str] = set()


def reset() -> None:
    _CONNECTIONS.clear()
    _PUSH.clear()
    _BOUNCES.clear()
    _SUPPRESS.clear()


def connect_oauth_mailbox(*, user_id: str, provider: str, refresh_token: str) -> dict[str, Any]:
    if provider not in {"imap", "smtp", "google", "microsoft"}:
        raise ValueError("unsupported provider")
    row = {
        "userId": user_id,
        "provider": provider,
        "status": "connected",
        "refreshTokenPresent": bool(refresh_token),
        "protocol": "oauth2",
        "connectedAt": utc_now(),
    }
    _CONNECTIONS[user_id] = row
    return row


def classify_message(subject: str, body: str = "") -> dict[str, Any]:
    text = f"{subject}\n{body}".lower()
    label = "other"
    if any(word in text for word in ("offer", "compensation package", "start date")):
        label = "offer"
    elif any(word in text for word in ("interview", "calendar invite", "zoom", "teams meeting")):
        label = "interview"
    elif any(word in text for word in ("nurture", "talent community", "stay in touch")):
        label = "nurture"
    elif any(word in text for word in ("unfortunately", "not moving forward", "rejected")):
        label = "reject"
    elif any(word in text for word in ("following up", "just checking", "any update")):
        label = "followup"
    return {"label": label, "confidence": 0.82 if label != "other" else 0.4}


_DT = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2})")


def parse_invite(raw: str, *, fallback_tz: str = "UTC") -> dict[str, Any]:
    match = _DT.search(raw or "")
    when = None
    if match:
        when = datetime.fromisoformat(match.group(1).replace(" ", "T")).replace(tzinfo=timezone.utc)
    else:
        try:
            when = parsedate_to_datetime(raw)
        except Exception:
            when = None
    return {
        "startsAt": when.isoformat() if when else None,
        "timezone": fallback_tz,
        "kind": "interview" if when else "unparsed",
        "needsManual": when is None,
    }


def digest_window(kind: str, *, now: datetime | None = None) -> dict[str, Any]:
    clock = now or datetime.now(timezone.utc)
    if kind == "daily":
        start = clock.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif kind == "weekly":
        start = (clock - timedelta(days=clock.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    else:
        raise ValueError("kind")
    return {"kind": kind, "start": start.isoformat(), "end": end.isoformat()}


def build_digest(events: list[dict[str, Any]], *, kind: str = "daily") -> dict[str, Any]:
    window = digest_window(kind)
    return {
        **window,
        "subject": f"AJAS {kind} digest ({len(events)} events)",
        "items": events[:50],
        "count": len(events),
    }


def subscribe_push(*, user_id: str, endpoint: str, keys: dict[str, str]) -> dict[str, Any]:
    if not endpoint.startswith("https://"):
        raise ValueError("endpoint must be https")
    row = {"userId": user_id, "endpoint": endpoint, "keys": dict(keys), "createdAt": utc_now()}
    _PUSH[user_id] = row
    return row


def bounce(address: str, *, code: str, permanent: bool) -> dict[str, Any]:
    email = address.strip().lower()
    row = {"email": email, "code": code, "permanent": bool(permanent), "at": utc_now()}
    _BOUNCES[email] = row
    if permanent or code.startswith("5"):
        _SUPPRESS.add(email)
    return row


def suppressed(address: str) -> bool:
    return address.strip().lower() in _SUPPRESS


def deliverability(domain: str) -> dict[str, Any]:
    host = domain.strip().lower()
    return {
        "domain": host,
        "spf": f"v=spf1 include:_spf.{host} ~all",
        "dkim": f"selector1._domainkey.{host}",
        "dmarc": f"v=DMARC1; p=quarantine; rua=mailto:dmarc@{host}",
        "ready": bool(host and "." in host),
    }

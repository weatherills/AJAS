"""HTML sanitizer, context-aware PII, SSO scaffold, sessions, audit diffs, consent, CSP."""

from __future__ import annotations

import hashlib
import hmac
import html
import re
from typing import Any
from uuid import uuid4

from app.matching.keys import utc_now

_UNSAFE_TAGS = re.compile(r"</?(script|iframe|object|embed|link|meta|style)[^>]*>", re.I)
_EVENT_ATTR = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
_JS_URL = re.compile(r"javascript:", re.I)
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

_SESSIONS: dict[str, dict[str, Any]] = {}
_AUDIT: list[dict[str, Any]] = []
_CONSENT: dict[str, dict[str, Any]] = {}
_SECRETS: dict[str, dict[str, Any]] = {}
_SSO_STATES: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _SESSIONS.clear()
    _AUDIT.clear()
    _CONSENT.clear()
    _SECRETS.clear()
    _SSO_STATES.clear()


def sanitize_html(raw: str) -> str:
    text = _UNSAFE_TAGS.sub("", raw or "")
    text = _EVENT_ATTR.sub("", text)
    text = _JS_URL.sub("", text)
    return text


def escape_text(raw: str) -> str:
    return html.escape(raw or "", quote=True)


def redact_pii(payload: str, *, context: str = "log") -> str:
    text = payload or ""
    text = _SSN.sub("[ssn]", text)
    text = _EMAIL.sub("[email]", text)
    if context in {"log", "payload", "ops"}:
        text = _PHONE.sub("[phone]", text)
    return text


def rotate_secret(name: str, *, previous: str | None = None) -> dict[str, Any]:
    secret = uuid4().hex + uuid4().hex
    row = {
        "name": name,
        "version": (_SECRETS.get(name, {}).get("version") or 0) + 1,
        "checksum": hashlib.sha256(secret.encode()).hexdigest()[:16],
        "rotatedAt": utc_now(),
        "alert": previous is not None and previous == secret,
    }
    _SECRETS[name] = {**row, "value": secret, "previous": previous}
    return {k: v for k, v in row.items()}


def secret_drift(name: str, observed_checksum: str) -> bool:
    current = _SECRETS.get(name)
    if not current:
        return True
    return current["checksum"] != observed_checksum


def google_oauth_start(*, redirect_uri: str, tenant_id: str) -> dict[str, Any]:
    state = uuid4().hex
    _SSO_STATES[state] = {"tenantId": tenant_id, "redirectUri": redirect_uri, "at": utc_now()}
    return {
        "authorizationUrl": (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id=ajas-google&redirect_uri={redirect_uri}&state={state}&response_type=code&scope=openid%20email"
        ),
        "state": state,
        "protocol": "oidc",
        "samlMetadata": "/v1/sso/google/metadata",
    }


def google_oauth_finish(*, state: str, code: str, email: str) -> dict[str, Any]:
    row = _SSO_STATES.pop(state, None)
    if row is None:
        raise KeyError("invalid sso state")
    if not code:
        raise ValueError("missing code")
    return {"email": email, "tenantId": row["tenantId"], "provider": "google", "protocol": "oidc"}


def create_session(*, user_id: str, device: str, ip: str) -> dict[str, Any]:
    token = uuid4().hex
    row = {
        "id": token,
        "userId": user_id,
        "device": device,
        "ip": ip,
        "createdAt": utc_now(),
        "revoked": False,
    }
    _SESSIONS[token] = row
    return row


def list_sessions(user_id: str) -> list[dict[str, Any]]:
    return [row for row in _SESSIONS.values() if row["userId"] == user_id and not row["revoked"]]


def revoke_session(session_id: str, *, user_id: str) -> bool:
    row = _SESSIONS.get(session_id)
    if not row or row["userId"] != user_id:
        return False
    row["revoked"] = True
    return True


def audit_diff(*, actor: str, entity: str, entity_id: str, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes = []
    keys = sorted(set(before) | set(after))
    for key in keys:
        if before.get(key) != after.get(key):
            changes.append({"field": key, "from": before.get(key), "to": after.get(key)})
    event = {
        "at": utc_now(),
        "actor": actor,
        "entity": entity,
        "entityId": entity_id,
        "changes": changes,
    }
    _AUDIT.append(event)
    return event


def recent_audit(limit: int = 50) -> list[dict[str, Any]]:
    return list(_AUDIT[-limit:])


COOKIE_KEYS = ("necessary", "analytics", "marketing")


def set_consent(user_id: str, choices: dict[str, bool]) -> dict[str, Any]:
    row = {key: bool(choices.get(key, key == "necessary")) for key in COOKIE_KEYS}
    row["necessary"] = True
    saved = {"userId": user_id, "choices": row, "updatedAt": utc_now(), "version": "ajas.consent.v1"}
    _CONSENT[user_id] = saved
    return saved


def export_consent_log(user_id: str | None = None) -> list[dict[str, Any]]:
    rows = list(_CONSENT.values())
    if user_id:
        rows = [row for row in rows if row["userId"] == user_id]
    return rows


SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; connect-src 'self' https://graph.microsoft.com https://login.microsoftonline.com; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "X-AJAS-Version": "sprint12",
}


def sign_webhook(secret: str, body: str, *, timestamp: str) -> str:
    digest = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_webhook(secret: str, body: str, header: str, *, now_ts: int, max_age: int = 300) -> bool:
    parts = dict(item.split("=", 1) for item in header.split(",") if "=" in item)
    try:
        ts = int(parts.get("t") or "0")
    except ValueError:
        return False
    if abs(now_ts - ts) > max_age:
        return False
    expected = hmac.new(secret.encode(), f"{parts.get('t')}.{body}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts.get("v1") or "")

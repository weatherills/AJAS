"""HMAC signatures for ingestion and apply webhooks."""

from __future__ import annotations

import hashlib
import hmac


def sign_payload(secret: str, body: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, body: str, header: str) -> bool:
    expected = sign_payload(secret, body)
    provided = (header or "").strip()
    return hmac.compare_digest(expected, provided)


def signed_event(secret: str, event_type: str, payload: dict) -> dict:
    import json

    body = json.dumps({"type": event_type, "payload": payload}, sort_keys=True, default=str)
    return {
        "type": event_type,
        "payload": payload,
        "signature": sign_payload(secret, body),
    }

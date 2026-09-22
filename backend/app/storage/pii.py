"""Field-level PII policy: encrypt, mask, and redact Cosmos documents."""

from __future__ import annotations

import hashlib
from typing import Any

from app.settings.crypto import open_token, seal_token

# Paths that must never leave the DAL in the clear.
ENCRYPT_PATHS: dict[str, tuple[str, ...]] = {
    "email_connections": ("access_token_enc", "refresh_token_enc"),
    "user_settings": ("token_blob",),
    "candidates": ("email", "phone"),
    "recruiters": ("email", "phone"),
    "oauth_credentials": ("access_token", "refresh_token", "secret"),
    "webhooks_outbound": ("secret",),
}

MASK_PATHS: dict[str, tuple[str, ...]] = {
    "users": ("email",),
    "email_accounts": ("address", "smtp_address"),
    "email_connections": ("account_email",),
    "email_messages": ("from_address", "to_addresses", "body_text", "body_html", "body", "from", "to"),
    "email_recipients": ("address",),
    "resumes": ("original_filename", "rawJson", "text", "text_preview"),
    "resume_parse_events": ("snapshot", "rawJson", "text"),
    "resume_versions": ("rawJson", "text"),
    "job_postings_raw": ("payload", "text", "body"),
    "match_evidence": ("sentences", "snippet", "text"),
    "cover_letters": ("body",),
    "candidates": ("email", "phone"),
    "recruiters": ("email", "phone"),
    "attachments": ("filename",),
    "oauth_credentials": ("access_token", "refresh_token"),
}

REDACT_ALWAYS: tuple[str, ...] = ("access_token", "refresh_token", "password", "cosmos_key")


def hash_text(value: str | None) -> str:
    """SHA-256 hex of a payload. Empty input stays empty so callers can skip storage."""
    if not value:
        return ""
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def pii_paths(container: str) -> tuple[str, ...]:
    encrypt = ENCRYPT_PATHS.get(container, ())
    mask = MASK_PATHS.get(container, ())
    return tuple(dict.fromkeys((*encrypt, *mask)))


def mask_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [mask_value(item) for item in value]
    text = str(value)
    if "@" in text:
        local, _, domain = text.partition("@")
        return (local[:1] + "***@" + domain) if domain else "***"
    if len(text) <= 4:
        return "***"
    return text[:2] + "***"


def encrypt_fields(container: str, doc: dict[str, Any], *, secret: str) -> dict[str, Any]:
    out = dict(doc)
    for path in ENCRYPT_PATHS.get(container, ()):
        if path in out and out[path] is not None:
            out[path] = seal_token(str(out[path]), secret)
    return out


def decrypt_fields(container: str, doc: dict[str, Any], *, secret: str) -> dict[str, Any]:
    out = dict(doc)
    for path in ENCRYPT_PATHS.get(container, ()):
        if path in out and out[path] is not None:
            out[path] = open_token(str(out[path]), secret)
    return out


def redact(container: str, doc: dict[str, Any], *, decrypt: bool = False, secret: str = "") -> dict[str, Any]:
    out = decrypt_fields(container, dict(doc), secret=secret) if decrypt else dict(doc)
    for path in REDACT_ALWAYS:
        out.pop(path, None)
    for path in MASK_PATHS.get(container, ()):
        if path in out:
            out[path] = mask_value(out[path])
    for path in ENCRYPT_PATHS.get(container, ()):
        if path in out and out[path] is not None and not decrypt:
            out[path] = "[redacted]"
    return out

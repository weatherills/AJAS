"""PII-safe audit + telemetry for LinkedIn ingest and Easy Apply."""

from __future__ import annotations

from typing import Any

from app.job_sources.keys import utc_now
from app.privacy_review import has_raw_pii, scrub_v2

AUDIT_EVENTS = (
    "fetch",
    "fetch_page",
    "deduped",
    "skipped_private",
    "skipped_expired",
    "retry",
    "rate_limited",
    "circuit_open",
    "apply",
    "submitted",
    "failed",
    "throttled",
    "captcha",
    "challenge",
    "timeout",
    "validation_failed",
    "session_expired",
    "blocked",
)

DROP_KEYS = frozenset(
    {
        "email",
        "phone",
        "token",
        "cookie",
        "cookies",
        "li_at",
        "password",
        "secret",
        "resume",
        "resume_text",
        "cover_letter",
        "authorization",
        "ssn",
        "fieldsSent",
        "answers",
        "data",
        "html",
        "page",
    }
)


def sanitize(payload: Any) -> Any:
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if key in DROP_KEYS or key.lower() in DROP_KEYS:
                continue
            out[key] = sanitize(value)
        return scrub_v2(out)
    if isinstance(payload, list):
        return [sanitize(item) for item in payload]
    if isinstance(payload, str):
        return scrub_v2(payload)
    return payload


_EVENTS: list[dict[str, Any]] = []


def reset() -> None:
    _EVENTS.clear()


def events() -> list[dict[str, Any]]:
    return list(_EVENTS)


def record(event: str, **payload: Any) -> dict[str, Any]:
    name = event if event in AUDIT_EVENTS else "fetch"
    row = sanitize({"event": name, "at": utc_now(), "source": "linkedin", **payload})
    if not isinstance(row, dict):
        row = {"event": name, "at": utc_now(), "source": "linkedin"}
    _EVENTS.append(row)
    return row


def assert_pii_safe(row: dict[str, Any]) -> bool:
    blob = str(row)
    if any(key in row for key in DROP_KEYS):
        return False
    return not has_raw_pii(blob)

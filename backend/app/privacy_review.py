"""PII redaction review for logs and outbound payloads."""

from __future__ import annotations

import re
from typing import Any

from app.mail.pii import redact_pii

_CC = re.compile(r"\b(?:\d[ -]*?){13,16}\b")


def redact_text(text: str | None) -> str:
    value = redact_pii(text)
    return _CC.sub("[redacted-cc]", value)


def review_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return {key: review_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [review_payload(item) for item in payload]
    if isinstance(payload, str):
        return redact_text(payload)
    return payload


def has_raw_pii(text: str | None) -> bool:
    sample = text or ""
    return "@" in sample or bool(_CC.search(sample))

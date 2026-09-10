"""Redact emails, phones, and similar PII from logs and expired mail bodies."""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d().\-\s]{8,}\d)")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def redact_pii(text: str | None) -> str:
    value = text or ""
    value = EMAIL_RE.sub("[redacted-email]", value)
    value = SSN_RE.sub("[redacted-ssn]", value)
    value = PHONE_RE.sub("[redacted-phone]", value)
    return value

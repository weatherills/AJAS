"""Hard validations for Auto-Apply payloads before they enter the queue."""

from __future__ import annotations

import re
from typing import Any

from app.auto_apply.errors import AutoApplyValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9().\-\s]{7,20}$")


def _answers(body: dict[str, Any]) -> dict[str, Any]:
    raw = body.get("answers")
    return raw if isinstance(raw, dict) else {}


def validate_apply_fields(body: dict[str, Any], profile: dict[str, str]) -> None:
    answers = _answers(body)
    name = str(answers.get("full_name") or answers.get("name") or profile.get("full_name") or profile.get("name") or "").strip()
    email = str(answers.get("email") or profile.get("email") or "").strip()
    phone = str(answers.get("phone") or profile.get("phone") or "").strip()
    if len(name) < 2:
        raise AutoApplyValidationError("Full name is required", path="full_name")
    if not EMAIL_RE.match(email):
        raise AutoApplyValidationError("A valid email is required", path="email")
    if phone and not PHONE_RE.match(phone):
        raise AutoApplyValidationError("Phone number looks invalid", path="phone")


def retry_backoff_seconds(dequeue_count: int) -> float:
    attempt = max(1, int(dequeue_count))
    return float(min(60, 2**attempt))

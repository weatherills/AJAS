"""Hard validations for Auto-Apply payloads before they enter the queue."""

from __future__ import annotations

import re
from typing import Any

from app.auto_apply.errors import AutoApplyValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# E.164 after normalizing separators (Backend PRD).
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")
ISO_LOCATION_RE = re.compile(
    r"^(?:[A-Z]{2}(?:-[A-Z0-9]{1,3})?|[A-Za-z][A-Za-z .,'-]{1,80}(?:,\s*[A-Za-z]{2,}(?:-[A-Za-z]{2})?)?)$"
)


def _answers(body: dict[str, Any]) -> dict[str, Any]:
    raw = body.get("answers")
    return raw if isinstance(raw, dict) else {}


def normalize_e164(phone: str) -> str:
    raw = (phone or "").strip()
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return "+" + digits if digits else ""


def validate_phone(phone: str, *, path: str = "phone") -> None:
    cleaned = normalize_e164(phone)
    if not cleaned or not E164_RE.match(cleaned):
        raise AutoApplyValidationError("Phone must be E.164 (e.g. +15555550100)", path=path)


def validate_location(location: str, *, path: str = "location") -> None:
    value = (location or "").strip()
    if not value:
        return
    if not ISO_LOCATION_RE.match(value):
        raise AutoApplyValidationError(
            "Location must be an ISO country/region code or a City, Region label",
            path=path,
        )


def validate_work_history(answers: dict[str, Any]) -> None:
    experience = answers.get("experience") or answers.get("work_history")
    if not isinstance(experience, list):
        return
    for index, row in enumerate(experience):
        if not isinstance(row, dict):
            continue
        start = str(row.get("start") or row.get("startDate") or "").strip()
        end = str(row.get("end") or row.get("endDate") or "").strip()
        if not start or not end:
            continue
        if end.lower() in {"present", "current", "now"}:
            continue
        if start > end:
            raise AutoApplyValidationError(
                "Work history dates are not coherent (start must be on or before end)",
                path=f"experience.{index}",
            )


def validate_apply_fields(body: dict[str, Any], profile: dict[str, str]) -> None:
    answers = _answers(body)
    name = str(answers.get("full_name") or answers.get("name") or profile.get("full_name") or profile.get("name") or "").strip()
    email = str(answers.get("email") or profile.get("email") or "").strip()
    phone = str(answers.get("phone") or profile.get("phone") or "").strip()
    location = str(answers.get("location") or profile.get("location") or "").strip()
    if len(name) < 2:
        raise AutoApplyValidationError("Full name is required", path="full_name")
    if not EMAIL_RE.match(email):
        raise AutoApplyValidationError("A valid email is required", path="email")
    if phone:
        validate_phone(phone)
    if location:
        validate_location(location)
    validate_work_history(answers)


def retry_backoff_seconds(dequeue_count: int) -> float:
    attempt = max(1, int(dequeue_count))
    return float(min(60, 2**attempt))

"""LinkedIn Easy Apply: mapping, attachments, Q&A, receipts, throttle, captcha HITL."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.auto_apply.attachments import validate_attachment
from app.auto_apply.captcha import detect as detect_captcha
from app.auto_apply.errors import AutoApplyValidationError
from app.auto_apply.field_map import apply_mapping, mapping_for, set_override
from app.flags import feature_enabled
from app.integrations.ingest import classify_error, retry_with_backoff, throttle
from app.job_sources.keys import utc_now

EASY_APPLY_FLAG = "linkedin_easy_apply"
EASY_APPLY_SITE = "linkedin"

DEFAULT_PROFILE_MAP = {
    "full_name": "name",
    "email": "email",
    "phone": "phone",
    "location": "location",
    "resume": "resume",
    "cover_letter": "coverLetter",
    "linkedin_url": "linkedinProfile",
}

QUESTION_TEMPLATES = {
    "work_authorization": "Yes, authorized to work.",
    "years_experience": "8",
    "sponsorship": "No sponsorship required.",
    "start_date": "Two weeks notice.",
    "salary_expectation": "Open to the posted range.",
    "willing_to_relocate": "Yes, for the right role.",
}

_RECEIPTS: list[dict[str, Any]] = []
_AUDIT: list[dict[str, Any]] = []


def reset() -> None:
    _RECEIPTS.clear()
    _AUDIT.clear()


def receipts() -> list[dict[str, Any]]:
    return list(_RECEIPTS)


def audit_log() -> list[dict[str, Any]]:
    return list(_AUDIT)


def _audit(event: str, **payload: Any) -> dict[str, Any]:
    row = {"event": event, "at": utc_now(), **payload}
    _AUDIT.append(row)
    return row


def ensure_linkedin_mapping() -> dict[str, str]:
    current = mapping_for(EASY_APPLY_SITE)
    if current.get("full_name") != "name" or "cover_letter" not in current:
        set_override(EASY_APPLY_SITE, {**DEFAULT_PROFILE_MAP, **current})
    return mapping_for(EASY_APPLY_SITE)


def map_fields(profile: dict[str, str], *, extras: dict[str, str] | None = None) -> dict[str, str]:
    ensure_linkedin_mapping()
    merged = dict(profile)
    if extras:
        merged.update({k: v for k, v in extras.items() if v})
    mapped = apply_mapping(EASY_APPLY_SITE, merged)
    for src, dest in DEFAULT_PROFILE_MAP.items():
        if src in merged and merged[src] and dest not in mapped:
            mapped[dest] = merged[src]
    return mapped


def answer_questions(questions: list[dict[str, Any]] | dict[str, Any] | None, *, approved: dict[str, str] | None = None) -> dict[str, str]:
    templates = {**QUESTION_TEMPLATES, **(approved or {})}
    items: list[dict[str, Any]]
    if isinstance(questions, dict):
        items = [{"id": key, "prompt": key, "key": key} for key in questions]
        # keep provided values as overrides
        templates = {**templates, **{str(k): str(v) for k, v in questions.items() if v is not None}}
    else:
        items = list(questions or [])
    answers: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or item.get("id") or item.get("prompt") or "").strip()
        if not key:
            continue
        slug = key.lower().replace(" ", "_")
        value = (
            item.get("answer")
            or templates.get(key)
            or templates.get(slug)
            or next((templates[k] for k in templates if k in slug or slug in k), None)
        )
        if value:
            answers[key] = str(value)
    return answers


def _attachments_meta(attachments: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    meta: list[dict[str, Any]] = []
    for item in attachments or []:
        kind = str(item.get("kind") or item.get("type") or "resume")
        content_type = str(item.get("contentType") or item.get("content_type") or "application/pdf")
        data = item.get("data") or b""
        if isinstance(data, str):
            data = data.encode("utf-8")
        size = int(item.get("size") or len(data))
        validate_attachment(kind=kind if kind in {"resume", "coverLetter"} else "resume", content_type=content_type, size=size)
        meta.append(
            {
                "kind": kind,
                "name": str(item.get("name") or f"{kind}.pdf"),
                "contentType": content_type,
                "size": size,
            }
        )
    return meta


def submit(
    *,
    job: dict[str, Any],
    profile: dict[str, str],
    questions: list[dict[str, Any]] | dict[str, Any] | None = None,
    attachments: list[dict[str, Any]] | None = None,
    page: Any = None,
    statuses: list[int] | None = None,
    rate_cap: int = 10,
    approved_answers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Submit an Easy Apply package. Never solves CAPTCHA; receipts always logged."""
    if not feature_enabled(EASY_APPLY_FLAG) and not feature_enabled("linkedin_adapter"):
        _audit("blocked", reason="flag_off", jobId=job.get("id"))
        return {"status": "disabled", "reason": "flag_off", "receipt": None}

    captcha = detect_captcha(page if page is not None else job)
    if captcha["captcha"]:
        receipt = _store_receipt(job, {}, [], {}, status="needs_manual", reason="captcha")
        _audit("captcha", jobId=job.get("id"), receiptId=receipt["receiptId"], bypass=False)
        return {
            "status": "needs_manual",
            "reason": "captcha",
            "hitl": True,
            "bypass": False,
            "receipt": receipt,
        }

    gate = throttle("linkedin_easy_apply", cap=rate_cap, jitter=0.0)
    if not gate["allowed"]:
        receipt = _store_receipt(job, {}, [], {}, status="rate_limited", reason="cap")
        _audit("throttled", jobId=job.get("id"), receiptId=receipt["receiptId"], used=gate["used"])
        return {"status": "rate_limited", "reason": "cap", "receipt": receipt, "throttle": gate}

    try:
        fields = map_fields(profile)
        answers = answer_questions(questions, approved=approved_answers)
        files = _attachments_meta(attachments)
    except AutoApplyValidationError as exc:
        receipt = _store_receipt(job, {}, [], {}, status="failed", reason=str(exc))
        _audit("validation_failed", jobId=job.get("id"), error=str(exc))
        return {"status": "failed", "reason": str(exc), "receipt": receipt}

    if not fields.get("email") or not fields.get("name"):
        receipt = _store_receipt(job, fields, files, answers, status="failed", reason="missing_required_fields")
        return {"status": "failed", "reason": "missing_required_fields", "receipt": receipt}

    retry = retry_with_backoff(statuses or [200], jitter=0.0)
    final = retry["final"]
    if final["action"] == "needs_manual":
        status = "needs_manual"
    elif final["class"] == "rate_limited":
        status = "rate_limited"
    elif final["class"] in {"permanent", "transient"} and final["action"] != "continue":
        status = "failed" if not final.get("retryable") else "rate_limited"
        if final["class"] == "transient" and retry["attempts"] and retry["attempts"][-1]["class"] != "ok":
            status = "failed"
    else:
        status = "submitted"

    # last attempt ok wins
    if retry["attempts"] and retry["attempts"][-1].get("class") == "ok":
        status = "submitted"

    receipt = _store_receipt(job, fields, files, answers, status=status, reason=final["class"])
    _audit("submitted" if status == "submitted" else status, jobId=job.get("id"), receiptId=receipt["receiptId"])
    return {"status": status, "reason": final["class"], "receipt": receipt, "retry": retry, "throttle": gate}


def _store_receipt(
    job: dict[str, Any],
    fields: dict[str, Any],
    files: list[dict[str, Any]],
    answers: dict[str, str],
    *,
    status: str,
    reason: str,
) -> dict[str, Any]:
    confirmation = None
    if status == "submitted":
        confirmation = f"EA-{uuid4().hex[:10].upper()}"
    row = {
        "receiptId": str(uuid4()),
        "jobId": job.get("id"),
        "sourcePostingId": job.get("sourcePostingId") or job.get("id"),
        "postingUrl": job.get("postingUrl") or job.get("applyUrl"),
        "company": job.get("company"),
        "title": job.get("title"),
        "confirmation": confirmation,
        "submittedAt": utc_now(),
        "fieldsSent": dict(fields),
        "attachments": [item.get("name") for item in files],
        "answers": dict(answers),
        "status": status,
        "reason": reason,
    }
    _RECEIPTS.append(row)
    return row

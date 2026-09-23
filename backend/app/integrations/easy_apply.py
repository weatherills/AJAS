"""LinkedIn Easy Apply: mapping, attachments, Q&A, receipts, throttle, captcha HITL."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.auto_apply.attachments import validate_attachment
from app.auto_apply.errors import AutoApplyValidationError
from app.auto_apply.field_map import apply_mapping, mapping_for, set_override
from app.flags import feature_enabled
from app.integrations import linkedin_audit
from app.integrations.ingest import retry_with_backoff, throttle
from app.integrations.linkedin_spec import (
    ATTACHMENT_SPEC,
    ERROR_MATRIX,
    RATE_PLAN,
    bump,
    classify_field_error,
    detect_challenge,
    error_payload,
    listing_visibility,
    render_cover_letter,
)
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
    linkedin_audit.record(event if event in linkedin_audit.AUDIT_EVENTS else "apply", **payload)
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
            answers[key] = str(value)[: int(ATTACHMENT_SPEC["answers"]["maxChars"])]
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
        validate_attachment(
            kind=kind if kind in {"resume", "coverLetter"} else "resume",
            content_type=content_type,
            size=size,
            data=data if isinstance(data, (bytes, bytearray)) else None,
            filename=str(item.get("name") or f"{kind}.pdf"),
        )
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
    rate_cap: int | None = None,
    approved_answers: dict[str, str] | None = None,
    account_id: str | None = None,
    live: bool = False,
) -> dict[str, Any]:
    """Submit an Easy Apply package. Never solves CAPTCHA; receipts always logged."""
    cap = int(rate_cap if rate_cap is not None else RATE_PLAN["easy_apply"]["capPerWindow"])
    bump("requests")
    if not feature_enabled(EASY_APPLY_FLAG) and not feature_enabled("linkedin_adapter"):
        _audit("blocked", reason="flag_off", jobId=job.get("id"))
        return {"status": "disabled", "reason": "flag_off", "code": "FLAG_OFF", "receipt": None, **error_payload("FLAG_OFF")}

    vis = listing_visibility(job)
    if not vis["visible"]:
        code = "PRIVATE_JOB" if vis["reason"] == "private" else "EXPIRED_JOB"
        receipt = _store_receipt(job, {}, [], {}, status="failed", reason=vis["reason"])
        _audit("failed", jobId=job.get("id"), code=code)
        return {"status": "failed", "reason": vis["reason"], "code": code, "receipt": receipt, **error_payload(code)}

    if account_id:
        from app.integrations.linkedin_session import STORE

        snapshot = STORE.public(account_id)
        if snapshot["status"] in {"expired", "revoked", "anonymous"}:
            receipt = _store_receipt(job, {}, [], {}, status="needs_manual", reason="session_expired")
            _audit("session_expired", jobId=job.get("id"), accountId=account_id)
            return {
                "status": "needs_manual",
                "reason": "session_expired",
                "code": "SESSION_EXPIRED",
                "receipt": receipt,
                **error_payload("SESSION_EXPIRED"),
            }

    challenge = detect_challenge(page if page is not None else {}, status=None)
    if challenge["kind"] in {"captcha", "challenge"}:
        code = str(challenge["code"] or "CAPTCHA")
        receipt = _store_receipt(job, {}, [], {}, status="needs_manual", reason=challenge["kind"])
        _audit(challenge["kind"], jobId=job.get("id"), receiptId=receipt["receiptId"], bypass=False)
        return {
            "status": "needs_manual",
            "reason": challenge["kind"],
            "hitl": True,
            "bypass": False,
            "abort": True,
            "code": code,
            "userPrompt": challenge["userPrompt"],
            "receipt": receipt,
        }

    if challenge["kind"] == "timeout":
        retry = retry_with_backoff(statuses or [408, 408, 408, 408], jitter=0.0, payload=page)
        receipt = _store_receipt(job, {}, [], {}, status="failed", reason="timeout")
        _audit("timeout", jobId=job.get("id"), receiptId=receipt["receiptId"])
        return {
            "status": "failed",
            "reason": "timeout",
            "code": "TIMEOUT",
            "userPrompt": challenge["userPrompt"],
            "retry": retry,
            "receipt": receipt,
            **error_payload("TIMEOUT"),
        }

    gate = throttle("linkedin_easy_apply", cap=cap, jitter=0.0)
    if not gate["allowed"]:
        receipt = _store_receipt(job, {}, [], {}, status="rate_limited", reason="cap")
        _audit("throttled", jobId=job.get("id"), receiptId=receipt["receiptId"], used=gate["used"])
        return {
            "status": "rate_limited",
            "reason": "cap",
            "code": "RATE_LIMIT",
            "receipt": receipt,
            "throttle": gate,
            **error_payload("RATE_LIMIT"),
        }

    files_in = list(attachments or [])
    if str(profile.get("cover_letter_mode") or "") == "generate" and not any(
        str(item.get("kind") or "") == "coverLetter" for item in files_in
    ):
        text = render_cover_letter(job=job, profile=profile)
        files_in.append(
            {
                "kind": "coverLetter",
                "name": "cover.txt",
                "contentType": "text/plain",
                "data": text.encode("utf-8"),
            }
        )

    field_error = classify_field_error(profile, files_in)
    if field_error:
        receipt = _store_receipt(job, {}, [], {}, status="failed", reason=field_error)
        _audit("validation_failed", jobId=job.get("id"), code=field_error)
        return {
            "status": "failed",
            "reason": field_error,
            "code": field_error,
            "receipt": receipt,
            **error_payload(field_error),
        }

    try:
        fields = map_fields(profile)
        answers = answer_questions(questions, approved=approved_answers)
        files = _attachments_meta(files_in)
    except AutoApplyValidationError as exc:
        lowered = str(exc).lower()
        if "antivirus" in lowered:
            code = "ATTACHMENT_VIRUS"
        elif "smaller" in lowered:
            code = "ATTACHMENT_SIZE"
        else:
            code = "ATTACHMENT_TYPE"
        receipt = _store_receipt(job, {}, [], {}, status="failed", reason=str(exc))
        _audit("validation_failed", jobId=job.get("id"), error=str(exc), code=code)
        return {"status": "failed", "reason": str(exc), "code": code, "receipt": receipt, **error_payload(code)}

    if not fields.get("email") or not fields.get("name"):
        receipt = _store_receipt(job, fields, files, answers, status="failed", reason="missing_required_fields")
        return {
            "status": "failed",
            "reason": "missing_required_fields",
            "code": "MISSING_REQUIRED",
            "receipt": receipt,
            **error_payload("MISSING_REQUIRED"),
        }

    retry = retry_with_backoff(statuses or [200], jitter=0.0, payload=page)
    final = retry["final"]
    if final["action"] == "needs_manual":
        status = "needs_manual"
    elif final["class"] == "rate_limited":
        status = "rate_limited"
    elif final["class"] in {"permanent", "transient", "timeout"} and final["action"] != "continue":
        status = "failed" if not final.get("retryable") else "rate_limited"
        if final["class"] in {"transient", "timeout"} and retry["attempts"] and retry["attempts"][-1]["class"] != "ok":
            status = "failed"
    else:
        status = "submitted"

    if retry["attempts"] and retry["attempts"][-1].get("class") == "ok":
        status = "submitted"

    if live and status == "submitted":
        from app.integrations.linkedin_client import deliver_application

        delivery = deliver_application(
            job,
            fields,
            files_in,
            answers,
            account_id=account_id,
            live=True,
        )
        if delivery.get("bypass") is True:
            delivery = {**delivery, "bypass": False, "status": "needs_manual", "reason": "captcha"}
        if delivery.get("status") != "submitted":
            status = str(delivery.get("status") or "failed")
            receipt = _store_receipt(job, fields, files, answers, status=status, reason=str(delivery.get("reason") or status))
            _audit(status if status in {"needs_manual", "failed", "rate_limited"} else "failed", jobId=job.get("id"), receiptId=receipt["receiptId"], bypass=False)
            return {
                "status": status,
                "reason": delivery.get("reason"),
                "code": delivery.get("code"),
                "userPrompt": delivery.get("userPrompt"),
                "hitl": delivery.get("hitl"),
                "abort": delivery.get("abort"),
                "bypass": False,
                "liveFetch": delivery.get("liveFetch"),
                "receipt": receipt,
                "retry": retry,
                "throttle": gate,
            }
        if delivery.get("confirmation"):
            # filled below via receipt
            confirmation_override = str(delivery["confirmation"])
        else:
            confirmation_override = None
    else:
        confirmation_override = None

    if status == "submitted":
        bump("submitted")
    else:
        bump("failed")

    receipt = _store_receipt(job, fields, files, answers, status=status, reason=final["class"], confirmation=confirmation_override)
    _audit("submitted" if status == "submitted" else status, jobId=job.get("id"), receiptId=receipt["receiptId"])
    return {
        "status": status,
        "reason": final["class"],
        "receipt": receipt,
        "retry": retry,
        "throttle": gate,
        "userPrompt": final.get("userPrompt") or ERROR_MATRIX.get(str(final.get("class") or "").upper(), {}).get("user"),
    }


def _store_receipt(
    job: dict[str, Any],
    fields: dict[str, Any],
    files: list[dict[str, Any]],
    answers: dict[str, str],
    *,
    status: str,
    reason: str,
    confirmation: str | None = None,
) -> dict[str, Any]:
    if status == "submitted":
        confirmation = confirmation or f"EA-{uuid4().hex[:10].upper()}"
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

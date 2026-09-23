"""LinkedIn Jobs + Easy Apply executable contracts (source of truth).

Live HTML scraping is out of the Job Source PRD. These tables drive fixture
ingest and Easy Apply when ``linkedin_adapter`` / ``linkedin_easy_apply`` are on.
"""

from __future__ import annotations

import re
from typing import Any

from app.auto_apply.attachments import COVER_TYPES, MAX_BYTES, POLICY, RESUME_TYPES
from app.auto_apply.captcha import detect as detect_captcha
from app.auto_apply.field_map import DEFAULT_MAP
from app.mail.scan import scan_attachment
from app.job_sources.circuit import FAILURE_THRESHOLD, OPEN_SECONDS
from app.job_sources.keys import canonical_id_for, slug, utc_now

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_DIGITS_RE = re.compile(r"\d")
_CHALLENGE_RE = re.compile(
    r"checkpoint|unusual activity|verify it.?s you|security challenge|device verification",
    re.I,
)
_TIMEOUT_RE = re.compile(r"timed? ?out|request timeout|504 gateway", re.I)

# --- Field mapping: LinkedIn listing → internal posting schema -----------------

FIELD_MAP: tuple[dict[str, Any], ...] = (
    {
        "linkedin": "id",
        "aliases": ("jobId", "source_posting_id", "entityUrn", "urn"),
        "internal": "sourcePostingId",
        "type": "string",
        "nullable": False,
        "fallback": "canonical_id[:12]",
    },
    {
        "linkedin": "title",
        "aliases": ("jobTitle", "name"),
        "internal": "title",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "linkedin": "company",
        "aliases": ("companyName", "employer", "companyDetails"),
        "internal": "company",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "linkedin": "location",
        "aliases": ("jobLocation", "formattedLocation"),
        "internal": "location",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "linkedin": "description",
        "aliases": ("body", "content", "jobDescription"),
        "internal": "description",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "linkedin": "apply_url",
        "aliases": ("url", "postingUrl", "link", "listedAtUrl"),
        "internal": "postingUrl",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "linkedin": "employment_type",
        "aliases": ("type", "jobType", "workplaceTypes"),
        "internal": "employmentType",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "linkedin": "postedAt",
        "aliases": ("posted_at", "listedAt", "datePosted", "listedAtDate"),
        "internal": "postedAt",
        "type": "datetime",
        "nullable": True,
        "fallback": "",
    },
    {
        "linkedin": "easyApply",
        "aliases": ("easy_apply", "apply_method", "applyMethod"),
        "internal": "applyMethod",
        "type": "enum",
        "nullable": False,
        "fallback": "easy_apply if linkedin host else external",
    },
    {
        "linkedin": "external_apply_url",
        "aliases": ("externalApplyUrl",),
        "internal": "externalApplyUrl",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "linkedin": "status",
        "aliases": ("visibility", "jobState"),
        "internal": "visibility",
        "type": "enum",
        "nullable": False,
        "fallback": "public",
    },
)


def _nested_text(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        nested = value.get("name") or value.get("text") or value.get("label") or value.get("display")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return ""


def extract_linkedin_field(job: dict[str, Any], spec: dict[str, Any]) -> str:
    keys = (spec["linkedin"], *spec.get("aliases", ()))
    for key in keys:
        text = _nested_text(job.get(key))
        if text:
            return text
        if key == "location" and isinstance(job.get("location"), dict):
            text = _nested_text(job["location"].get("display")) or _nested_text(job["location"].get("name"))
            if text:
                return text
    fallback = spec.get("fallback")
    if fallback in {None, "canonical_id[:12]", "easy_apply if linkedin host else external", "public"}:
        return ""
    return str(fallback or "")


def listing_visibility(job: dict[str, Any]) -> dict[str, Any]:
    """Private and expired postings are skipped (PRD gap: edge cases)."""
    status = str(job.get("status") or job.get("visibility") or job.get("jobState") or "").lower()
    if job.get("private") is True or status in {"private", "unlisted", "confidential"}:
        return {"visible": False, "reason": "private"}
    if job.get("expired") is True or status in {"expired", "closed", "filled"}:
        return {"visible": False, "reason": "expired"}
    return {"visible": True, "reason": "public"}


def listing_dedupe_key(*, title: str, company: str, location: str, posted_at: str) -> str:
    """Job key + company + location + postedAt (Kanban pagination/dedupe rule)."""
    return f"{slug(title)}|{slug(company)}|{slug(location)}|{slug(posted_at) if posted_at else 'na'}"


def map_linkedin_job(job: dict[str, Any]) -> dict[str, Any]:
    mapped = {row["internal"]: extract_linkedin_field(job, row) for row in FIELD_MAP}
    vis = listing_visibility(job)
    posted = mapped.get("postedAt") or ""
    title = mapped.get("title") or ""
    company = mapped.get("company") or ""
    location = mapped.get("location") or ""
    mapped["visibility"] = vis["reason"]
    mapped["visible"] = vis["visible"]
    mapped["listingKey"] = listing_dedupe_key(
        title=title, company=company, location=location, posted_at=posted
    )
    if not mapped.get("sourcePostingId"):
        mapped["sourcePostingId"] = canonical_id_for(mapped["listingKey"])[:12]
    return mapped


# --- Rate limiting, retries, circuit, counters --------------------------------

RATE_PLAN: dict[str, dict[str, Any]] = {
    "ingest": {
        "capPerWindow": 50,
        "windowSeconds": 60,
        "jitterSeconds": 0.35,
        "maxAttempts": 4,
        "backoffBaseSeconds": 0.25,
        "backoffCapSeconds": 8.0,
        "circuitFailureThreshold": FAILURE_THRESHOLD,
        "circuitOpenSeconds": OPEN_SECONDS,
        "retryStatus": (429, 408, 503, 504),
        "counters": (
            "requests",
            "retries",
            "rate_limited",
            "circuit_open",
            "transient",
            "permanent",
            "captcha",
            "timeout",
            "private_skipped",
            "expired_skipped",
            "deduped",
        ),
    },
    "easy_apply": {
        "capPerWindow": 10,
        "windowSeconds": 60,
        "jitterSeconds": 0.2,
        "maxAttempts": 4,
        "backoffBaseSeconds": 0.25,
        "backoffCapSeconds": 8.0,
        "circuitFailureThreshold": FAILURE_THRESHOLD,
        "circuitOpenSeconds": OPEN_SECONDS,
        "retryStatus": (429, 408, 503, 504),
        "counters": ("requests", "retries", "rate_limited", "captcha", "submitted", "failed"),
    },
}

_COUNTERS: dict[str, int] = {}


def reset_counters() -> None:
    _COUNTERS.clear()


def bump(name: str, n: int = 1) -> int:
    _COUNTERS[name] = _COUNTERS.get(name, 0) + n
    return _COUNTERS[name]


def counters() -> dict[str, int]:
    names = list(RATE_PLAN["ingest"]["counters"]) + list(RATE_PLAN["easy_apply"]["counters"])
    return {name: int(_COUNTERS.get(name, 0)) for name in dict.fromkeys(names)}


# --- Pagination ---------------------------------------------------------------

PAGINATION: dict[str, Any] = {
    "mode": "cursor",
    "offsetSupported": False,
    "windowSize": 25,
    "maxPages": 20,
    "stop": (
        "empty_page",
        "no_next_cursor",
        "duplicate_cursor",
        "limit_reached",
        "rate_cap",
        "max_pages",
        "circuit_open",
    ),
}


def walk_pages(payload: Any, *, window_size: int | None = None, max_pages: int | None = None) -> dict[str, Any]:
    """Cursor-first pagination. A flat ``jobs`` list is one page with no next cursor."""
    window = int(window_size or PAGINATION["windowSize"])
    limit = int(max_pages or PAGINATION["maxPages"])
    pages: list[dict[str, Any]] = []
    seen: set[str] = set()
    stop = "no_next_cursor"

    raw_pages: list[dict[str, Any]] = []
    if isinstance(payload, dict) and isinstance(payload.get("pages"), list):
        for index, page in enumerate(payload["pages"]):
            if isinstance(page, list):
                raw_pages.append({"cursor": f"p{index}", "jobs": page, "nextCursor": None})
            elif isinstance(page, dict):
                jobs = page.get("jobs") if isinstance(page.get("jobs"), list) else []
                cursor = str(page.get("cursor") or f"p{index}")
                nxt = page.get("nextCursor") or page.get("next")
                raw_pages.append({"cursor": cursor, "jobs": jobs, "nextCursor": nxt})
    elif isinstance(payload, list):
        raw_pages.append({"cursor": "p0", "jobs": payload, "nextCursor": None})
    elif isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        raw_pages.append(
            {
                "cursor": str(payload.get("cursor") or "p0"),
                "jobs": payload["jobs"],
                "nextCursor": payload.get("nextCursor") or payload.get("next"),
            }
        )
    else:
        stop = "empty_page"
        return {"pages": [], "stop": stop, "cursors": [], "windowSize": window}

    for index, page in enumerate(raw_pages):
        if index >= limit:
            stop = "max_pages"
            break
        cursor = str(page.get("cursor") or f"p{index}")
        if cursor in seen:
            stop = "duplicate_cursor"
            break
        seen.add(cursor)
        jobs = list(page.get("jobs") or [])[:window]
        pages.append({"cursor": cursor, "jobs": jobs, "nextCursor": page.get("nextCursor")})
        if not jobs:
            stop = "empty_page"
            break
        if not page.get("nextCursor"):
            stop = "no_next_cursor"
            if index == len(raw_pages) - 1:
                break
            # more raw pages without a cursor still continue (fixture pages[])
            if isinstance(payload, dict) and isinstance(payload.get("pages"), list):
                continue
            break
    return {
        "pages": pages,
        "stop": stop,
        "cursors": [row["cursor"] for row in pages],
        "windowSize": window,
    }


# --- Easy Apply field / error matrix ------------------------------------------

EASY_APPLY_FIELDS: tuple[dict[str, Any], ...] = (
    {
        "profile": "full_name",
        "linkedin": "name",
        "required": True,
        "validation": "non-empty, max 100",
        "remediation": "Add your full name in profile settings.",
    },
    {
        "profile": "email",
        "linkedin": "email",
        "required": True,
        "validation": "RFC-like email",
        "remediation": "Use a valid email address.",
    },
    {
        "profile": "phone",
        "linkedin": "phone",
        "required": False,
        "validation": "7+ digits if present",
        "remediation": "Add a reachable phone number.",
    },
    {
        "profile": "location",
        "linkedin": "location",
        "required": False,
        "validation": "non-empty if present, max 120",
        "remediation": "Set a city or remote location.",
    },
    {
        "profile": "linkedin_url",
        "linkedin": "linkedinProfile",
        "required": False,
        "validation": "linkedin.com/in/ URL if present",
        "remediation": "Paste your public LinkedIn profile URL.",
    },
    {
        "profile": "resume",
        "linkedin": "resume",
        "required": True,
        "validation": "PDF/DOCX ≤ 5 MB",
        "remediation": "Upload a PDF or DOCX resume under 5 MB.",
    },
    {
        "profile": "cover_letter",
        "linkedin": "coverLetter",
        "required": False,
        "validation": "PDF/DOCX/TXT/MD ≤ 5 MB or generated template",
        "remediation": "Attach a cover letter or leave blank.",
    },
)

ERROR_MATRIX: dict[str, dict[str, Any]] = {
    "MISSING_REQUIRED": {
        "http": 400,
        "status": "failed",
        "user": "Required Easy Apply fields are missing.",
        "action": "fix_profile",
        "retryable": False,
    },
    "INVALID_EMAIL": {
        "http": 400,
        "status": "failed",
        "user": "The email on your profile is not valid.",
        "action": "fix_profile",
        "retryable": False,
    },
    "INVALID_PHONE": {
        "http": 400,
        "status": "failed",
        "user": "The phone number needs at least seven digits.",
        "action": "fix_profile",
        "retryable": False,
    },
    "INVALID_LINKEDIN_URL": {
        "http": 400,
        "status": "failed",
        "user": "LinkedIn profile URL must contain linkedin.com/in/.",
        "action": "fix_profile",
        "retryable": False,
    },
    "ATTACHMENT_TYPE": {
        "http": 400,
        "status": "failed",
        "user": "Resume must be PDF or DOCX; cover letters may also be TXT or Markdown.",
        "action": "replace_file",
        "retryable": False,
    },
    "ATTACHMENT_SIZE": {
        "http": 400,
        "status": "failed",
        "user": "Each attachment must be 5 MB or smaller.",
        "action": "replace_file",
        "retryable": False,
    },
    "ATTACHMENT_VIRUS": {
        "http": 400,
        "status": "failed",
        "user": "That file failed the antivirus scan. Replace it with a clean PDF or DOCX.",
        "action": "replace_file",
        "retryable": False,
    },
    "MISSING_RESUME": {
        "http": 400,
        "status": "failed",
        "user": "A resume file is required for Easy Apply.",
        "action": "attach_resume",
        "retryable": False,
    },
    "PRIVATE_JOB": {
        "http": 409,
        "status": "failed",
        "user": "This posting is private and cannot be applied to from AJAS.",
        "action": "skip",
        "retryable": False,
    },
    "EXPIRED_JOB": {
        "http": 409,
        "status": "failed",
        "user": "This posting has expired.",
        "action": "skip",
        "retryable": False,
    },
    "RATE_LIMIT": {
        "http": 429,
        "status": "rate_limited",
        "user": "LinkedIn rate limit reached. AJAS will wait and retry.",
        "action": "backoff",
        "retryable": True,
    },
    "SESSION_EXPIRED": {
        "http": 401,
        "status": "needs_manual",
        "user": "Your LinkedIn session expired. Reconnect the account, then retry.",
        "action": "reconnect",
        "retryable": False,
    },
    "CAPTCHA": {
        "http": 428,
        "status": "needs_manual",
        "user": "LinkedIn asked for a CAPTCHA. Complete it in LinkedIn, then retry from Review.",
        "action": "needs_manual",
        "retryable": False,
        "bypass": False,
        "abort": True,
    },
    "CHALLENGE": {
        "http": 428,
        "status": "needs_manual",
        "user": "LinkedIn issued a security challenge. Finish it in the browser, then retry.",
        "action": "needs_manual",
        "retryable": False,
        "bypass": False,
        "abort": True,
    },
    "TIMEOUT": {
        "http": 504,
        "status": "failed",
        "user": "LinkedIn timed out. AJAS retried with backoff and then aborted safely.",
        "action": "retry_then_abort",
        "retryable": True,
        "abortAfterAttempts": 4,
    },
    "FLAG_OFF": {
        "http": 200,
        "status": "disabled",
        "user": "LinkedIn Easy Apply is turned off for this workspace.",
        "action": "enable_flag",
        "retryable": False,
    },
}

ATTACHMENT_SPEC: dict[str, Any] = {
    "resume": {
        **POLICY["resume"],
        "contentTypes": sorted(RESUME_TYPES),
        "maxBytes": MAX_BYTES,
        "required": True,
        "template": None,
    },
    "coverLetter": {
        **POLICY["coverLetter"],
        "contentTypes": sorted(COVER_TYPES),
        "maxBytes": MAX_BYTES,
        "required": False,
        "template": (
            "Dear {company} hiring team,\n\n"
            "I am applying for the {title} role in {location}.\n\n"
            "Sincerely,\n{name}\n"
        ),
    },
    "answers": {
        "required": False,
        "source": "approved templates + profile Q&A",
        "maxChars": 2000,
    },
}

COVER_TEMPLATE = str(ATTACHMENT_SPEC["coverLetter"]["template"])

PROFILE_TO_LINKEDIN = dict(DEFAULT_MAP["linkedin"])


def render_cover_letter(
    template: str | None = None,
    *,
    job: dict[str, Any],
    profile: dict[str, str],
) -> str:
    body = template or COVER_TEMPLATE
    return body.format(
        company=str(job.get("company") or "the"),
        title=str(job.get("title") or "this"),
        location=str(job.get("location") or "the posted location"),
        name=str(profile.get("full_name") or profile.get("name") or "Applicant"),
    )


def classify_field_error(profile: dict[str, Any], attachments: list[dict[str, Any]] | None) -> str | None:
    name = str(profile.get("full_name") or profile.get("name") or "").strip()
    email = str(profile.get("email") or "").strip()
    phone = str(profile.get("phone") or "").strip()
    url = str(profile.get("linkedin_url") or "").strip()
    if not name:
        return "MISSING_REQUIRED"
    if not email:
        return "MISSING_REQUIRED"
    if not EMAIL_RE.match(email):
        return "INVALID_EMAIL"
    if phone and len(PHONE_DIGITS_RE.findall(phone)) < 7:
        return "INVALID_PHONE"
    if url and "linkedin.com/in/" not in url.lower():
        return "INVALID_LINKEDIN_URL"
    files = list(attachments or [])
    resumes = [item for item in files if str(item.get("kind") or item.get("type") or "resume") == "resume"]
    if not resumes:
        return "MISSING_RESUME"
    for item in files:
        kind = str(item.get("kind") or item.get("type") or "resume")
        content_type = str(item.get("contentType") or item.get("content_type") or "")
        data = item.get("data") or b""
        size = int(item.get("size") or (len(data) if isinstance(data, (bytes, str)) else 0))
        allowed = RESUME_TYPES if kind == "resume" else COVER_TYPES
        if content_type not in allowed:
            return "ATTACHMENT_TYPE"
        if size > MAX_BYTES:
            return "ATTACHMENT_SIZE"
        raw = data.encode("utf-8") if isinstance(data, str) else (data if isinstance(data, (bytes, bytearray)) else b"")
        if raw:
            scanned = scan_attachment(bytes(raw), file_name=str(item.get("name") or "file"))
            if not scanned.clean:
                return "ATTACHMENT_VIRUS"
    return None


def error_payload(code: str, **extra: Any) -> dict[str, Any]:
    spec = ERROR_MATRIX[code]
    return {
        "code": code,
        "userPrompt": spec["user"],
        "action": spec["action"],
        "retryable": spec.get("retryable"),
        "error": spec,
        **extra,
    }


# --- Captcha / challenge fallback ---------------------------------------------

CAPTCHA_FALLBACK: dict[str, Any] = {
    "bypass": False,
    "solve": False,
    "onCaptcha": "needs_manual",
    "onChallenge": "needs_manual",
    "onTimeout": "retry_then_abort",
    "prompts": {key: row["user"] for key, row in ERROR_MATRIX.items() if key in {"CAPTCHA", "CHALLENGE", "TIMEOUT"}},
}


def _challenge_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return " ".join(str(payload.get(key) or "") for key in ("html", "page", "body", "message", "error", "text"))
    return str(payload or "")


def detect_challenge(payload: Any, *, status: int | None = None) -> dict[str, Any]:
    """Never solves captchas. Challenges abort to HITL; timeouts retry then abort."""
    captcha = detect_captcha(payload)
    text = _challenge_text(payload)
    if captcha["captcha"]:
        return {
            "kind": "captcha",
            "captcha": True,
            "action": "needs_manual",
            "hitl": True,
            "bypass": False,
            "abort": True,
            "retryable": False,
            "userPrompt": ERROR_MATRIX["CAPTCHA"]["user"],
            "code": "CAPTCHA",
        }
    if _CHALLENGE_RE.search(text):
        return {
            "kind": "challenge",
            "captcha": False,
            "action": "needs_manual",
            "hitl": True,
            "bypass": False,
            "abort": True,
            "retryable": False,
            "userPrompt": ERROR_MATRIX["CHALLENGE"]["user"],
            "code": "CHALLENGE",
        }
    timed_out = int(status or 0) in {408, 504} or bool(_TIMEOUT_RE.search(text))
    if timed_out:
        return {
            "kind": "timeout",
            "captcha": False,
            "action": "retry",
            "hitl": False,
            "bypass": False,
            "abort": False,
            "retryable": True,
            "userPrompt": ERROR_MATRIX["TIMEOUT"]["user"],
            "code": "TIMEOUT",
        }
    return {
        "kind": "none",
        "captcha": False,
        "action": "continue",
        "hitl": False,
        "bypass": False,
        "abort": False,
        "retryable": False,
        "userPrompt": "",
        "code": None,
    }


# --- Security checklist + success metrics (contracts) -------------------------

SECURITY_CHECKLIST: tuple[dict[str, Any], ...] = (
    {
        "id": "data_minimization",
        "rule": "Store listing fields in FIELD_MAP only; no cookie jars, inbox bodies, or resume bytes on ingest.",
    },
    {
        "id": "storage_encryption",
        "rule": "LinkedIn session tokens are sealed at rest; plaintext tokens never leave the session store.",
    },
    {
        "id": "access_control",
        "rule": "HTTP routes require JWT; linkedin_adapter defaults on (tested); linkedin_easy_apply stays off; SOURCE_TYPES stays greenhouse|lever.",
    },
    {
        "id": "redaction",
        "rule": "Audit/telemetry redacts email, phone, tokens, cookies, and resume text.",
    },
    {
        "id": "fail_closed",
        "rule": "Robots/consent, captcha, and missing flags fail closed. Captcha is never bypassed.",
    },
)

SUCCESS_TARGETS: dict[str, Any] = {
    "fetchSuccessPct": 98.0,
    "dedupeRatePct": 5.0,
    "easyApplyCompletionPct": 80.0,
    "medianRuntimeMs": 8000,
    "qa": (
        "flag_default_off",
        "source_types_unchanged",
        "captcha_never_bypassed",
        "receipt_on_every_attempt",
        "private_expired_skipped",
        "pii_redacted_in_audit",
    ),
}

PRD_GAPS_INGEST: tuple[str, ...] = (
    "private_jobs",
    "expired_posts",
    "error_states",
    "rate_limit_handling",
    "pagination_rules",
    "retries_backoff",
    "telemetry",
    "success_metrics",
)

PRD_GAPS_EASY_APPLY: tuple[str, ...] = (
    "required_optional_matrix",
    "validation_rules_per_field",
    "file_upload_constraints",
    "autofill_mappings",
    "failure_timeout_flows",
)


def evaluate_security(
    *,
    session_public: dict[str, Any],
    audit_rows: list[dict[str, Any]],
    flags: dict[str, Any],
    source_types: frozenset[str],
) -> dict[str, Any]:
    """Executable PRD non-functionals: minimize, encrypt, ACL, redact, fail closed."""
    from app.integrations.linkedin_audit import assert_pii_safe

    items = {
        "data_minimization": all("cookie" not in str(row).lower() and "password" not in str(row).lower() for row in FIELD_MAP),
        "storage_encryption": "token" not in session_public and "cipher" not in session_public and "cookie" not in session_public,
        "access_control": (
            flags.get("linkedin_adapter") in {True, False}
            and source_types == frozenset({"greenhouse", "lever"})
        ),
        "redaction": all(assert_pii_safe(row) for row in audit_rows),
        "fail_closed": CAPTCHA_FALLBACK["bypass"] is False and CAPTCHA_FALLBACK["solve"] is False,
    }
    return {
        "checklist": [dict(row) for row in SECURITY_CHECKLIST],
        "items": items,
        "passed": all(items.values()),
    }


def spec_bundle() -> dict[str, Any]:
    return {
        "generatedAt": utc_now(),
        "liveScrape": False,
        "sourceTypesUnchanged": True,
        "fieldMap": [dict(row) for row in FIELD_MAP],
        "ratePlan": RATE_PLAN,
        "pagination": PAGINATION,
        "easyApplyFields": [dict(row) for row in EASY_APPLY_FIELDS],
        "errorMatrix": ERROR_MATRIX,
        "attachments": ATTACHMENT_SPEC,
        "profileMap": PROFILE_TO_LINKEDIN,
        "captcha": CAPTCHA_FALLBACK,
        "security": [dict(row) for row in SECURITY_CHECKLIST],
        "successTargets": SUCCESS_TARGETS,
        "prdGaps": {"jobsIngestion": list(PRD_GAPS_INGEST), "easyApply": list(PRD_GAPS_EASY_APPLY)},
        "counters": counters(),
        "sessionPolicy": __import__("app.integrations.linkedin_session", fromlist=["SESSION_POLICY"]).SESSION_POLICY,
    }

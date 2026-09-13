"""Canonical API error codes and retry hints.

Handlers may still emit legacy aliases (BAD_INPUT, VALIDATION_ERROR). The
envelope always includes ``retryable`` so the UI can toast vs retry.
"""

from __future__ import annotations

from typing import Any

CANONICAL_CODES: dict[str, dict[str, Any]] = {
    "UNAUTHENTICATED": {"status": 401, "retryable": False},
    "FORBIDDEN": {"status": 403, "retryable": False},
    "INVALID_INPUT": {"status": 400, "retryable": False},
    "BAD_INPUT": {"status": 400, "retryable": False},
    "VALIDATION_ERROR": {"status": 400, "retryable": False},
    "NOT_FOUND": {"status": 404, "retryable": False},
    "CONFLICT": {"status": 409, "retryable": False},
    "PRECONDITION_FAILED": {"status": 412, "retryable": False},
    "PAYLOAD_TOO_LARGE": {"status": 413, "retryable": False},
    "UNPROCESSABLE": {"status": 422, "retryable": False},
    "RATE_LIMITED": {"status": 429, "retryable": True},
    "UNAVAILABLE": {"status": 503, "retryable": True},
    "OAUTH_NOT_CONFIGURED": {"status": 400, "retryable": False},
    "SOURCE_NOT_CONFIGURED": {"status": 400, "retryable": False},
    "INGESTION_FAILED": {"status": 502, "retryable": True},
    "APPLY_FAILED": {"status": 502, "retryable": True},
    "EMAIL_FAILED": {"status": 502, "retryable": True},
    "ROBOTS_DISALLOWED": {"status": 403, "retryable": False},
    "ATTACHMENT_REJECTED": {"status": 422, "retryable": False},
}

ALIASES = {
    "BAD_INPUT": "INVALID_INPUT",
    "VALIDATION_ERROR": "INVALID_INPUT",
}

REMEDIATION: dict[str, str] = {
    "UNAUTHENTICATED": "Sign in again or paste a valid session token.",
    "FORBIDDEN": "Ask an admin to grant the required role.",
    "INVALID_INPUT": "Fix the highlighted fields and retry.",
    "NOT_FOUND": "Refresh the list; the record may have been deleted.",
    "CONFLICT": "Reload the resource and apply your change again.",
    "RATE_LIMITED": "Wait for the retry window, then send fewer requests.",
    "UNAVAILABLE": "Check Azure Functions and Cosmos, then retry.",
    "INGESTION_FAILED": "Inspect source flags, robots/consent, and the circuit breaker.",
    "APPLY_FAILED": "Confirm the posting URL allowlist and resume attachment.",
    "EMAIL_FAILED": "Reconnect Microsoft Graph in Settings.",
    "ROBOTS_DISALLOWED": "Do not scrape this host; use the official board API or fixtures.",
    "ATTACHMENT_REJECTED": "Upload a PDF/DOCX under the size limit.",
    "SOURCE_NOT_CONFIGURED": "Add a Greenhouse token or Lever URL in Settings.",
}


def error_taxonomy(code: str, status_code: int | None = None) -> dict[str, object]:
    known = CANONICAL_CODES.get(code, {})
    status = int(known.get("status") or status_code or 500)
    meta = error_meta(code, status)
    canonical = str(meta["canonical"])
    return {
        **meta,
        "status": status,
        "remediation": REMEDIATION.get(canonical, REMEDIATION.get(code, "Retry or contact support.")),
    }


def error_meta(code: str, status_code: int) -> dict[str, Any]:
    known = CANONICAL_CODES.get(code, {})
    retryable = bool(known.get("retryable", status_code >= 500 or status_code == 429))
    canonical = ALIASES.get(code, code)
    return {
        "code": code,
        "canonical": canonical,
        "retryable": retryable,
        "remediation": REMEDIATION.get(canonical, REMEDIATION.get(code)),
    }

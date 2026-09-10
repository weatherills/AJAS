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
}

ALIASES = {
    "BAD_INPUT": "INVALID_INPUT",
    "VALIDATION_ERROR": "INVALID_INPUT",
}


def error_meta(code: str, status_code: int) -> dict[str, Any]:
    known = CANONICAL_CODES.get(code, {})
    retryable = bool(known.get("retryable", status_code >= 500 or status_code == 429))
    canonical = ALIASES.get(code, code)
    return {
        "code": code,
        "canonical": canonical,
        "retryable": retryable,
    }

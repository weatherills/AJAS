"""HTTP helpers shared by feature blueprints.

A single JSON response shape and error envelope keep endpoints consistent as
they are added in later phases.
"""
import json
from typing import Any

import azure.functions as func

from app.errors import error_meta
from app.request_context import current_request_id


def _base_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    request_id = current_request_id()
    if request_id:
        headers["X-Request-Id"] = request_id
    if extra:
        headers.update({key: str(value) for key, value in extra.items() if value is not None})
    return headers


def json_response(
    payload: Any,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> func.HttpResponse:
    """Serialize ``payload`` to a JSON HTTP response."""
    return func.HttpResponse(
        json.dumps(payload, default=str),
        status_code=status_code,
        mimetype="application/json",
        headers=_base_headers(headers),
    )


def error_response(
    code: str,
    message: str,
    status_code: int,
    details: Any = None,
    *,
    retry_after: int | None = None,
    headers: dict[str, str] | None = None,
) -> func.HttpResponse:
    """Return a standard error envelope: ``{"error": {code, message, details?, retryable}}``."""
    meta = error_meta(code, status_code)
    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "retryable": meta["retryable"],
        "canonical": meta["canonical"],
    }
    if details is not None:
        error["details"] = details
    extra = dict(headers or {})
    if retry_after is not None:
        extra["Retry-After"] = str(int(retry_after))
        if isinstance(details, dict) and "retryAfter" not in details:
            error["details"] = {**details, "retryAfter": int(retry_after)}
        elif details is None:
            error["details"] = {"retryAfter": int(retry_after)}
    if status_code == 429 and "Retry-After" not in extra:
        extra["Retry-After"] = "1"
    return json_response({"error": error}, status_code=status_code, headers=extra or None)

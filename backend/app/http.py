"""HTTP helpers shared by feature blueprints.

A single JSON response shape and error envelope keep endpoints consistent as
they are added in later phases.
"""
import json
from typing import Any

import azure.functions as func


def json_response(payload: Any, status_code: int = 200) -> func.HttpResponse:
    """Serialize ``payload`` to a JSON HTTP response."""
    return func.HttpResponse(
        json.dumps(payload, default=str),
        status_code=status_code,
        mimetype="application/json",
    )


def error_response(
    code: str,
    message: str,
    status_code: int,
    details: Any = None,
) -> func.HttpResponse:
    """Return a standard error envelope: ``{"error": {code, message, details?}}``."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return json_response({"error": error}, status_code=status_code)

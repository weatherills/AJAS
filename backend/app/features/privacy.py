"""Privacy request HTTP surface (GDPR tickets)."""

from __future__ import annotations

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.privacy import create_privacy_request, list_privacy_requests

bp = func.Blueprint()


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    raise exc


@bp.route(route="v1/privacy/requests", methods=["GET", "POST"])
def privacy_requests(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = get_principal(req)
        if req.method.upper() == "GET":
            items = list_privacy_requests(principal.user_id)
            return json_response({"items": items, "count": len(items)})
        try:
            body = req.get_json() or {}
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        row = create_privacy_request(
            principal.user_id,
            kind=str(body.get("kind") or "export"),
            note=str(body.get("note") or ""),
        )
        return json_response(row, status_code=201)
    except Exception as exc:
        return _handle(exc)

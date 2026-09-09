"""Settings HTTP API (Backend PRD)."""

from __future__ import annotations

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.settings.errors import SettingsConflictError, SettingsNotFoundError, SettingsValidationError
from app.settings.oauth import GraphError
from app.settings.runtime import get_service
from app.settings.service import SettingsRateLimitedError

bp = func.Blueprint()


def _auth(req: func.HttpRequest):
    return get_principal(req)


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, SettingsValidationError):
        pointer = f"/{exc.path}" if exc.path else None
        return error_response(
            "VALIDATION_ERROR",
            str(exc),
            400,
            details=[{"path": pointer, "message": str(exc)}] if pointer else None,
        )
    if isinstance(exc, SettingsNotFoundError):
        return error_response("NOT_FOUND", str(exc), 404)
    if isinstance(exc, SettingsConflictError):
        return error_response("CONFLICT", str(exc), 409)
    if isinstance(exc, GraphError):
        return error_response(exc.code, str(exc), exc.status_code)
    if isinstance(exc, SettingsRateLimitedError):
        return error_response("RATE_LIMITED", str(exc), 429)
    raise exc


def _json_body(req: func.HttpRequest) -> dict:
    try:
        body = req.get_json()
    except ValueError as exc:
        raise SettingsValidationError("JSON body required") from exc
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise SettingsValidationError("JSON object required")
    return body


@bp.route(route="v1/settings", methods=["GET"])
def get_settings(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(get_service().get(principal.user_id))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/settings", methods=["PATCH"])
def patch_settings(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(get_service().patch(principal.user_id, _json_body(req)))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/settings/email/connect", methods=["POST"])
def connect_email(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(get_service().connect(principal.user_id, _json_body(req)))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/settings/email/callback", methods=["POST"])
def email_callback(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(get_service().callback(principal.user_id, _json_body(req)))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/settings/email/disconnect", methods=["POST"])
def disconnect_email(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(get_service().disconnect(principal.user_id))
    except Exception as exc:
        return _handle(exc)

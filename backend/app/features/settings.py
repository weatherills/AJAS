"""Settings HTTP API (Backend PRD)."""

from __future__ import annotations

import json
from collections.abc import Callable

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.observability import log_exception, log_request
from app.settings.errors import SettingsConflictError, SettingsNotFoundError, SettingsValidationError
from app.settings.oauth import GraphError
from app.settings.runtime import get_service
from app.settings.service import (
    SettingsOAuthNotConfiguredError,
    SettingsRateLimitedError,
    SettingsSourceNotConfiguredError,
)

bp = func.Blueprint()
FEATURE = "settings"


def _auth(req: func.HttpRequest):
    return get_principal(req)


def _map_error(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, SettingsOAuthNotConfiguredError):
        return error_response("OAUTH_NOT_CONFIGURED", str(exc), 400)
    if isinstance(exc, SettingsSourceNotConfiguredError):
        return error_response("SOURCE_NOT_CONFIGURED", str(exc), 400)
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


def _run(req: func.HttpRequest, route: str, handler: Callable) -> func.HttpResponse:
    user_id: str | None = None
    try:
        principal = _auth(req)
        user_id = principal.user_id
        resp = handler(principal)
        log_request(
            feature=FEATURE,
            route=route,
            method=req.method,
            status=resp.status_code,
            user_id=user_id,
        )
        return resp
    except Exception as exc:
        log_exception(FEATURE, route, exc)
        resp = _map_error(exc)
        log_request(
            feature=FEATURE,
            route=route,
            method=req.method,
            status=resp.status_code,
            user_id=user_id,
            error=str(exc),
        )
        return resp


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
    return _run(
        req,
        "GET /v1/settings",
        lambda principal: json_response(get_service().get(principal.user_id)),
    )


@bp.route(route="v1/settings", methods=["PATCH"])
def patch_settings(req: func.HttpRequest) -> func.HttpResponse:
    return _run(
        req,
        "PATCH /v1/settings",
        lambda principal: json_response(get_service().patch(principal.user_id, _json_body(req))),
    )


@bp.route(route="v1/settings/email/connect", methods=["POST"])
def connect_email(req: func.HttpRequest) -> func.HttpResponse:
    return _run(
        req,
        "POST /v1/settings/email/connect",
        lambda principal: json_response(get_service().connect(principal.user_id, _json_body(req))),
    )


@bp.route(route="v1/settings/email/callback", methods=["POST"])
def email_callback(req: func.HttpRequest) -> func.HttpResponse:
    return _run(
        req,
        "POST /v1/settings/email/callback",
        lambda principal: json_response(get_service().callback(principal.user_id, _json_body(req))),
    )


@bp.route(route="v1/settings/email/disconnect", methods=["POST"])
def disconnect_email(req: func.HttpRequest) -> func.HttpResponse:
    return _run(
        req,
        "POST /v1/settings/email/disconnect",
        lambda principal: json_response(get_service().disconnect(principal.user_id)),
    )


@bp.queue_trigger(arg_name="msg", queue_name="match-recalc", connection="AzureWebJobsStorage")
def settings_match_recalc_job(msg: func.QueueMessage) -> None:
    get_service().apply_match_recalc(json.loads(msg.get_body().decode("utf-8")))


@bp.queue_trigger(arg_name="msg", queue_name="source-discovery", connection="AzureWebJobsStorage")
def settings_source_discovery_job(msg: func.QueueMessage) -> None:
    get_service().apply_source_discovery(json.loads(msg.get_body().decode("utf-8")))

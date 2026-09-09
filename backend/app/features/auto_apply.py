"""Auto-Apply HTTP APIs and request queue worker (runbook Phase 2)."""

from __future__ import annotations

import json

import azure.functions as func

from app.auth import AuthError, ForbiddenError, get_principal, require_scopes
from app.auto_apply.constants import READ_SCOPE, WRITE_SCOPE
from app.auto_apply.errors import (
    AutoApplyConflictError,
    AutoApplyNotFoundError,
    AutoApplyValidationError,
)
from app.auto_apply.runtime import get_service
from app.http import error_response, json_response

bp = func.Blueprint()


def _auth(req: func.HttpRequest, *scopes: str):
    principal = get_principal(req)
    if scopes:
        require_scopes(principal, *scopes)
    return principal


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, ForbiddenError):
        return error_response("FORBIDDEN", str(exc), 403)
    if isinstance(exc, AutoApplyValidationError):
        pointer = f"/{exc.path}" if getattr(exc, "path", None) else None
        return error_response(
            "INVALID_INPUT",
            str(exc),
            400,
            details=[{"path": pointer, "message": str(exc)}] if pointer else None,
        )
    if isinstance(exc, AutoApplyNotFoundError):
        return error_response("NOT_FOUND", str(exc), 404)
    if isinstance(exc, AutoApplyConflictError):
        details = {"request_id": exc.request_id} if getattr(exc, "request_id", None) else None
        return error_response("CONFLICT", str(exc), 409, details=details)
    raise exc


def _json_body(req: func.HttpRequest) -> dict:
    try:
        body = req.get_json()
    except ValueError as exc:
        raise AutoApplyValidationError("JSON body required") from exc
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise AutoApplyValidationError("JSON object required")
    return body


def _header(req: func.HttpRequest, *names: str) -> str | None:
    for name in names:
        value = req.headers.get(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _json_payload(msg: func.QueueMessage) -> dict:
    return json.loads(msg.get_body().decode("utf-8"))


@bp.route(route="v1/auto-apply/requests", methods=["POST"])
def auto_apply_create(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req, WRITE_SCOPE)
        status, body = get_service().create_request(
            principal.user_id,
            _json_body(req),
            idempotency_key=_header(req, "Idempotency-Key", "idempotency-key"),
        )
        return json_response(body, status_code=status)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/auto-apply/requests", methods=["GET"])
def auto_apply_list(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req, READ_SCOPE)
        body = get_service().list_requests(
            principal.user_id,
            status=req.params.get("state") or req.params.get("status") or None,
        )
        return json_response(body)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/auto-apply/requests/{request_id}", methods=["GET"])
def auto_apply_get(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req, READ_SCOPE)
        return json_response(get_service().get_request(principal.user_id, req.route_params["request_id"]))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/auto-apply/requests/{request_id}/cancel", methods=["POST"])
def auto_apply_cancel(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req, WRITE_SCOPE)
        status, body = get_service().cancel(principal.user_id, req.route_params["request_id"])
        return json_response(body, status_code=status)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/auto-apply/webhooks/{provider}", methods=["POST"])
def auto_apply_webhook(req: func.HttpRequest) -> func.HttpResponse:
    try:
        provider = (req.route_params.get("provider") or "").lower()
        body = get_service().ingest_webhook(
            provider,
            _json_body(req),
            secret=_header(req, "X-Webhook-Secret", "x-webhook-secret"),
        )
        return json_response(body, status_code=202)
    except Exception as exc:
        return _handle(exc)


@bp.queue_trigger(arg_name="msg", queue_name="auto-apply-requests", connection="AzureWebJobsStorage")
def auto_apply_process_queued(msg: func.QueueMessage) -> None:
    get_service().process_request(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)

"""Learning Loop HTTP API, queue workers, and daily tune timer."""

from __future__ import annotations

import json

import azure.functions as func

from app.auth import AuthError, ForbiddenError, get_principal
from app.http import error_response, json_response
from app.learning.errors import (
    LearningConflictError,
    LearningForbiddenError,
    LearningNotFoundError,
    LearningRateLimitedError,
    LearningStaleError,
    LearningValidationError,
)
from app.learning.runtime import get_service
from app.observability import log_exception, log_request

bp = func.Blueprint()


def _auth(req: func.HttpRequest):
    return get_principal(req)


def _is_admin(req: func.HttpRequest, principal) -> bool:
    header = (req.headers.get("X-Admin") or req.headers.get("x-admin") or "").strip().lower()
    return header in {"1", "true", "yes"} or "admin" in principal.scopes


def _handle(exc: Exception, *, route: str, method: str, user_id: str | None = None) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, (ForbiddenError, LearningForbiddenError)):
        log_request(feature="learning", route=route, method=method, status=403, user_id=user_id, error=str(exc))
        return error_response("FORBIDDEN", str(exc), 403)
    if isinstance(exc, LearningValidationError):
        pointer = f"/{exc.path}" if exc.path else None
        return error_response(
            "INVALID_INPUT",
            str(exc),
            400,
            details=[{"path": pointer, "message": str(exc)}] if pointer else None,
        )
    if isinstance(exc, (LearningNotFoundError, LearningStaleError)):
        return error_response("NOT_FOUND", str(exc), 404)
    if isinstance(exc, LearningConflictError):
        return error_response("CONFLICT", str(exc), 409)
    if isinstance(exc, LearningRateLimitedError):
        resp = error_response("RATE_LIMITED", str(exc), 429)
        return func.HttpResponse(resp.get_body(), status_code=429, mimetype="application/json", headers={"Retry-After": "1"})
    log_exception("learning", route, exc)
    raise exc


def _json_body(req: func.HttpRequest) -> dict:
    try:
        body = req.get_json()
    except ValueError as exc:
        raise LearningValidationError("JSON body required") from exc
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise LearningValidationError("JSON object required")
    return body


def _json_payload(msg: func.QueueMessage) -> dict:
    return json.loads(msg.get_body().decode("utf-8"))


@bp.route(route="v1/learning/decisions", methods=["POST"])
def log_learning_decision(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        status, body = get_service().log_decision(principal.user_id, _json_body(req))
        log_request(feature="learning", route="v1/learning/decisions", method="POST", status=status, user_id=principal.user_id)
        return json_response(body, status_code=status)
    except Exception as exc:
        return _handle(exc, route="v1/learning/decisions", method="POST")


@bp.route(route="v1/decisions", methods=["POST"])
def log_learning_decision_prd(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        status, body = get_service().log_decision(principal.user_id, _json_body(req))
        log_request(feature="learning", route="v1/decisions", method="POST", status=status, user_id=principal.user_id)
        return json_response(body, status_code=status)
    except Exception as exc:
        return _handle(exc, route="v1/decisions", method="POST")


@bp.route(route="v1/learning/params", methods=["GET"])
def get_learning_params(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        get_service().drain()
        body = get_service().params(principal.user_id)
        log_request(feature="learning", route="v1/learning/params", method="GET", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/learning/params", method="GET")


@bp.route(route="v1/learning/params", methods=["PATCH"])
def patch_learning_params(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().update_prefs(principal.user_id, _json_body(req))
        log_request(feature="learning", route="v1/learning/params", method="PATCH", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/learning/params", method="PATCH")


@bp.route(route="v1/learning/tune", methods=["POST"])
def tune_learning(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        if not _is_admin(req, principal):
            raise LearningForbiddenError("admin/service only")
        payload = _json_body(req)
        status, body = get_service().tune(
            payload.get("user_id") or payload.get("userId"),
            admin=True,
            window_days=payload.get("window_days") or payload.get("windowDays"),
            min_samples=payload.get("min_samples") or payload.get("minSamples"),
            force_activate=bool(payload.get("force_activate") or payload.get("forceActivate")),
        )
        log_request(feature="learning", route="v1/learning/tune", method="POST", status=status, user_id=principal.user_id)
        return json_response(body, status_code=status)
    except Exception as exc:
        return _handle(exc, route="v1/learning/tune", method="POST")


@bp.route(route="v1/metrics", methods=["GET"])
def get_learning_metrics(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        scope = (req.params.get("scope") or "self").lower()
        period = (req.params.get("period") or "7d").lower()
        admin = _is_admin(req, principal)
        get_service().drain()
        body = get_service().metrics(principal.user_id, scope=scope, period=period, admin=admin)
        log_request(feature="learning", route="v1/metrics", method="GET", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/metrics", method="GET")


@bp.queue_trigger(arg_name="msg", queue_name="learning-decisions", connection="AzureWebJobsStorage")
def learning_decisions_job(msg: func.QueueMessage) -> None:
    get_service().process_decision(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)


@bp.queue_trigger(arg_name="msg", queue_name="tuning-tasks", connection="AzureWebJobsStorage")
def learning_tune_job(msg: func.QueueMessage) -> None:
    get_service().process_tune(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)


@bp.timer_trigger(schedule="0 0 6 * * *", arg_name="timer", run_on_startup=False)
def learning_tune_timer(timer: func.TimerRequest) -> None:
    get_service().poll_all()

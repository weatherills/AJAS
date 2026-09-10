"""Review & Decision UI HTTP API and queue workers (Backend PRD)."""

from __future__ import annotations

import json
from collections.abc import Callable

import azure.functions as func

from app.auth import AuthError, ForbiddenError, get_principal, require_scopes
from app.http import error_response, json_response
from app.observability import log_exception, log_request
from app.review.constants import READ_SCOPE, WRITE_SCOPE
from app.review.errors import (
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewPreconditionError,
    ReviewValidationError,
)
from app.review.runtime import get_service
from app.tracing import finish_span, start_span

bp = func.Blueprint()
FEATURE = "review"


def _auth(req: func.HttpRequest, *scopes: str):
    principal = get_principal(req)
    if scopes:
        require_scopes(principal, *scopes)
    return principal


def _map_error(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, ForbiddenError):
        return error_response("FORBIDDEN", str(exc), 403)
    if isinstance(exc, ReviewValidationError):
        pointer = f"/{exc.path}" if exc.path else None
        return error_response(
            "INVALID_INPUT",
            str(exc),
            400,
            details=[{"path": pointer, "message": str(exc)}] if pointer else None,
        )
    if isinstance(exc, ReviewNotFoundError):
        return error_response("NOT_FOUND", str(exc), 404)
    if isinstance(exc, ReviewConflictError):
        return error_response("CONFLICT", str(exc), 409)
    if isinstance(exc, ReviewPreconditionError):
        return error_response("PRECONDITION_FAILED", str(exc), 412)
    raise exc


def _run(
    req: func.HttpRequest,
    route: str,
    *scopes: str,
    handler: Callable,
) -> func.HttpResponse:
    user_id: str | None = None
    try:
        principal = _auth(req, *scopes)
        user_id = principal.user_id
        span = start_span("review", route=route, method=req.method)
        resp = handler(principal)
        finish_span(span, ok=resp.status_code < 400)
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
        raise ReviewValidationError("JSON body required") from exc
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise ReviewValidationError("JSON object required")
    return body


def _query_float(value: str | None, path: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ReviewValidationError(f"invalid {path}", path=path) from exc


def _query_int(value: str | None, path: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ReviewValidationError(f"invalid {path}", path=path) from exc


def _header(req: func.HttpRequest, *names: str) -> str | None:
    for name in names:
        value = req.headers.get(name)
        if value is not None and value.strip():
            return value.strip()
    return None


def _idempotency_key(req: func.HttpRequest) -> str | None:
    return _header(req, "Idempotency-Key", "idempotency-key")


def _if_match(req: func.HttpRequest) -> str | None:
    value = _header(req, "If-Match", "if-match")
    if value is None:
        return None
    if value.startswith("W/"):
        value = value[2:].strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value or None


def _forwarded_ip(req: func.HttpRequest) -> str | None:
    raw = _header(req, "X-Forwarded-For", "x-forwarded-for")
    if not raw:
        return None
    return raw.split(",")[0].strip() or None


def _json_payload(msg: func.QueueMessage) -> dict:
    return json.loads(msg.get_body().decode("utf-8"))


@bp.route(route="v1/matches", methods=["GET"])
def list_matches(req: func.HttpRequest) -> func.HttpResponse:
    def handle(principal):
        body = get_service().list_matches(
            principal.user_id,
            status=req.params.get("status") or None,
            min_score=_query_float(req.params.get("minScore"), "minScore"),
            job_title=req.params.get("jobTitle") or None,
            company=req.params.get("company") or None,
            location=req.params.get("location") or None,
            source=req.params.get("source") or None,
            created_after=req.params.get("createdAfter") or None,
            page_size=_query_int(req.params.get("limit") or req.params.get("pageSize"), "pageSize"),
            continuation=req.params.get("cursor") or req.params.get("continuation") or None,
            include_archived=(req.params.get("includeArchived") or "").lower() in {"1", "true", "yes"},
        )
        return json_response(body)

    return _run(req, "GET /v1/matches", READ_SCOPE, handler=handle)


@bp.route(route="v1/matches/bulk", methods=["POST"])
def bulk_update_matches(req: func.HttpRequest) -> func.HttpResponse:
    def handle(principal):
        return json_response(get_service().bulk_update(principal.user_id, _json_body(req)))

    return _run(req, "POST /v1/matches/bulk", WRITE_SCOPE, handler=handle)


@bp.route(route="v1/matches/{matchId}", methods=["GET"])
def get_match(req: func.HttpRequest) -> func.HttpResponse:
    def handle(principal):
        return json_response(get_service().get_match(principal.user_id, req.route_params["matchId"]))

    return _run(req, "GET /v1/matches/{matchId}", READ_SCOPE, handler=handle)


@bp.route(route="v1/matches/{matchId}/decision", methods=["POST"])
def create_decision(req: func.HttpRequest) -> func.HttpResponse:
    def handle(principal):
        status, body = get_service().decide(
            principal.user_id,
            req.route_params["matchId"],
            _json_body(req),
            idempotency_key=_idempotency_key(req),
            etag=_if_match(req),
            ip=_forwarded_ip(req),
        )
        return json_response(body, status_code=status)

    return _run(req, "POST /v1/matches/{matchId}/decision", WRITE_SCOPE, handler=handle)


@bp.route(route="v1/matches/{matchId}/reopen", methods=["POST"])
def reopen_match(req: func.HttpRequest) -> func.HttpResponse:
    def handle(principal):
        return json_response(get_service().reopen(principal.user_id, req.route_params["matchId"]))

    return _run(req, "POST /v1/matches/{matchId}/reopen", WRITE_SCOPE, handler=handle)


@bp.route(route="v1/queue/saved-jobs", methods=["GET"])
def list_saved_jobs(req: func.HttpRequest) -> func.HttpResponse:
    def handle(principal):
        body = get_service().list_saved_jobs(
            principal.user_id,
            status=req.params.get("status") or "awaiting_decision",
            page_size=_query_int(req.params.get("pageSize"), "pageSize"),
            continuation=req.params.get("continuation") or None,
            sort=req.params.get("sort") or None,
            order=req.params.get("order") or None,
        )
        return json_response(body)

    return _run(req, "GET /v1/queue/saved-jobs", READ_SCOPE, handler=handle)


@bp.route(route="v1/decisions", methods=["GET"])
def list_decisions(req: func.HttpRequest) -> func.HttpResponse:
    def handle(principal):
        body = get_service().list_decisions(
            principal.user_id,
            match_id=req.params.get("matchId") or None,
            job_id=req.params.get("jobId") or None,
            decision=req.params.get("decision") or None,
            page_size=_query_int(req.params.get("pageSize"), "pageSize"),
            continuation=req.params.get("continuation") or None,
        )
        return json_response(body)

    return _run(req, "GET /v1/decisions", READ_SCOPE, handler=handle)


@bp.route(route="v1/decisions/history", methods=["GET"])
def decision_history(req: func.HttpRequest) -> func.HttpResponse:
    def handle(principal):
        body = get_service().history(
            principal.user_id,
            match_id=req.params.get("matchId") or None,
            job_id=req.params.get("jobId") or None,
            resume_id=req.params.get("resumeId") or None,
        )
        return json_response(body)

    return _run(req, "GET /v1/decisions/history", READ_SCOPE, handler=handle)


@bp.queue_trigger(arg_name="msg", queue_name="decision-events", connection="AzureWebJobsStorage")
def decision_events_job(msg: func.QueueMessage) -> None:
    get_service().process_decision_event(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)


@bp.queue_trigger(arg_name="msg", queue_name="review-enrich", connection="AzureWebJobsStorage")
def review_enrich_job(msg: func.QueueMessage) -> None:
    get_service().process_enrich_event(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)

"""Matching & Ranking HTTP API and queue worker (Backend PRD)."""

from __future__ import annotations

import json
import time

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.matching.errors import (
    MatchingConflictError,
    MatchingNotFoundError,
    MatchingPayloadTooLargeError,
    MatchingRateLimitedError,
    MatchingValidationError,
)
from app.matching.runtime import get_service
from app.slo import record_latency, snapshot as slo_snapshot

bp = func.Blueprint()


def _auth(req: func.HttpRequest):
    return get_principal(req)


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, MatchingValidationError):
        pointer = f"/{exc.path}" if exc.path else None
        return error_response(
            "INVALID_INPUT",
            str(exc),
            400,
            details=[{"path": pointer, "message": str(exc)}] if pointer else None,
        )
    if isinstance(exc, MatchingNotFoundError):
        return error_response("NOT_FOUND", str(exc), 404)
    if isinstance(exc, MatchingConflictError):
        return error_response("CONFLICT", str(exc), 409)
    if isinstance(exc, MatchingRateLimitedError):
        return error_response("RATE_LIMITED", str(exc), 429)
    if isinstance(exc, MatchingPayloadTooLargeError):
        return error_response("PAYLOAD_TOO_LARGE", str(exc), 413)
    raise exc


def _json_body(req: func.HttpRequest) -> dict:
    try:
        body = req.get_json()
    except ValueError as exc:
        raise MatchingValidationError("JSON body required") from exc
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise MatchingValidationError("JSON object required")
    return body


def _query_float(value: str | None, path: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise MatchingValidationError(f"invalid {path}", path=path) from exc


def _query_int(value: str | None, path: str, *, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise MatchingValidationError(f"invalid {path}", path=path) from exc


def _idempotency_key(req: func.HttpRequest) -> str | None:
    value = req.headers.get("Idempotency-Key") or req.headers.get("idempotency-key")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _json_payload(msg: func.QueueMessage) -> dict:
    return json.loads(msg.get_body().decode("utf-8"))


@bp.route(route="v1/matches/compute", methods=["POST"])
def compute_match(req: func.HttpRequest) -> func.HttpResponse:
    started = time.perf_counter()
    try:
        principal = _auth(req)
        status, body = get_service().compute(
            principal.user_id,
            _json_body(req),
            idempotency_key_header=_idempotency_key(req),
        )
        record_latency("POST /v1/matches/compute", (time.perf_counter() - started) * 1000)
        return json_response(body, status_code=status)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/matches/rank", methods=["POST"])
def rank_matches(req: func.HttpRequest) -> func.HttpResponse:
    started = time.perf_counter()
    try:
        principal = _auth(req)
        status, body = get_service().rank(
            principal.user_id,
            _json_body(req),
            idempotency_key_header=_idempotency_key(req),
        )
        record_latency("POST /v1/matches/rank", (time.perf_counter() - started) * 1000)
        return json_response(body, status_code=status)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/matches/warmup", methods=["POST"])
def warmup_matches(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(get_service().warmup(principal.user_id))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/matching/ab-variant", methods=["GET"])
def match_ab_variant(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(get_service().ab_assignment(principal.user_id))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/ops/slo", methods=["GET"])
def matching_slo(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _auth(req)
        return json_response(slo_snapshot())
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/match-results", methods=["GET"])
def list_match_results(req: func.HttpRequest) -> func.HttpResponse:
    # Review already owns GET /v1/matches (decision queue). Matching lists
    # persisted scores on a distinct path so both blueprints can coexist.
    try:
        principal = _auth(req)
        body = get_service().list_matches(
            principal.user_id,
            job_id=req.params.get("jobId") or None,
            resume_id=req.params.get("resumeId") or None,
            min_score=_query_float(req.params.get("minScore"), "minScore"),
            limit=_query_int(req.params.get("limit"), "limit", default=50),
            cursor=req.params.get("cursor") or None,
        )
        return json_response(body)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/operations/{operationId}", methods=["GET"])
def get_operation(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        service = get_service()
        # In-memory local queues have no Azure worker; drain so 202 polls complete.
        service.drain()
        return json_response(service.get_operation(principal.user_id, req.route_params["operationId"]))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/operations/{operationId}/cancel", methods=["POST"])
def cancel_operation(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(get_service().cancel(principal.user_id, req.route_params["operationId"]))
    except Exception as exc:
        return _handle(exc)


@bp.queue_trigger(arg_name="msg", queue_name="match-compute", connection="AzureWebJobsStorage")
def match_compute_job(msg: func.QueueMessage) -> None:
    get_service().process_compute(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)

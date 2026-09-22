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
from app.matching.records import get_record_store, match_record_id
from app.matching.runtime import get_service
from app.storage.dal import ConflictError
from app.ratelimit import rate_limit_headers
from app.slo import record_latency, snapshot as slo_snapshot
from app.tracing import finish_span, start_span

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
    if isinstance(exc, MatchingConflictError) or isinstance(exc, ConflictError):
        return error_response("CONFLICT", str(exc), 409)
    if isinstance(exc, MatchingRateLimitedError):
        retry_after = int(getattr(exc, "retry_after", 1) or 1)
        return error_response(
            "RATE_LIMITED",
            str(exc),
            429,
            retry_after=retry_after,
            headers=rate_limit_headers(limit=60, remaining=0, retry_after=retry_after),
        )
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
    span = start_span("matching.compute")
    try:
        principal = _auth(req)
        status, body = get_service().compute(
            principal.user_id,
            _json_body(req),
            idempotency_key_header=_idempotency_key(req),
        )
        record_latency("POST /v1/matches/compute", (time.perf_counter() - started) * 1000)
        finish_span(span, ok=True)
        return json_response(body, status_code=status)
    except Exception as exc:
        finish_span(span, ok=False, error=str(exc))
        return _handle(exc)


@bp.route(route="v1/matches/rank", methods=["POST"])
def rank_matches(req: func.HttpRequest) -> func.HttpResponse:
    started = time.perf_counter()
    span = start_span("matching.rank")
    try:
        principal = _auth(req)
        status, body = get_service().rank(
            principal.user_id,
            _json_body(req),
            idempotency_key_header=_idempotency_key(req),
        )
        record_latency("POST /v1/matches/rank", (time.perf_counter() - started) * 1000)
        finish_span(span, ok=True)
        return json_response(body, status_code=status)
    except Exception as exc:
        finish_span(span, ok=False, error=str(exc))
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
            sort=req.params.get("sort") or None,
            order=req.params.get("order") or "desc",
        )
        return json_response(body)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/match-results/{matchId}", methods=["GET"])
def get_match_result(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(get_service().get_match(principal.user_id, req.route_params["matchId"]))
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


@bp.route(route="v1/match-records", methods=["GET", "POST"])
def match_records(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        store = get_record_store()
        if req.method.upper() == "GET":
            items = store.list_records(
                principal.user_id,
                job_id=req.params.get("jobId") or None,
                resume_id=req.params.get("resumeId") or None,
            )
            return json_response({"items": items, "count": len(items)})
        body = _json_body(req)
        saved = store.upsert_score(
            user_id=principal.user_id,
            job_id=str(body.get("jobId") or ""),
            resume_id=str(body.get("resumeId") or ""),
            model_version=str(body.get("modelVersion") or "matching-v1"),
            score=float(body.get("score") or 0),
            evidence=list(body.get("evidence") or []),
            etag=body.get("etag") or body.get("_etag"),
        )
        return json_response(saved, status_code=201 if saved["status"] == "created" else 200)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/match-records/{matchId}", methods=["GET"])
def match_record_detail(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        store = get_record_store()
        match_id = req.route_params["matchId"]
        record = store.get(principal.user_id, match_id)
        return json_response({"record": record, "evidence": store.list_evidence(principal.user_id, match_id)})
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/match-records/{matchId}/rescore", methods=["POST"])
def match_record_rescore(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        store = get_record_store()
        current = store.get(principal.user_id, req.route_params["matchId"])
        body = _json_body(req)
        saved = store.upsert_score(
            user_id=principal.user_id,
            job_id=str(current.get("jobId")),
            resume_id=str(current.get("resumeId")),
            model_version=str(body.get("modelVersion") or current.get("modelVersion") or "matching-v1"),
            score=float(body.get("score") if body.get("score") is not None else current.get("score") or 0),
            evidence=list(body.get("evidence") or []),
        )
        return json_response(saved)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/matching/prune", methods=["POST"])
def match_records_prune(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        try:
            body = _json_body(req)
        except MatchingValidationError:
            body = {}
        keep = body.get("keep")
        result = get_record_store().prune(
            principal.user_id,
            keep=int(keep) if keep is not None else None,
            dry_run=bool(body.get("dryRun") or body.get("dry_run")),
        )
        return json_response(result)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/matching/batch-rescore", methods=["POST"])
def match_records_batch(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        try:
            body = _json_body(req)
        except MatchingValidationError:
            body = {}
        return json_response(get_record_store().batch_rescore(principal.user_id, list(body.get("pairs") or [])))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/matching/id", methods=["GET"])
def match_record_id_preview(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        return json_response(
            {
                "id": match_record_id(
                    user_id=principal.user_id,
                    job_id=str(req.params.get("jobId") or ""),
                    resume_id=str(req.params.get("resumeId") or ""),
                    model_version=str(req.params.get("modelVersion") or "matching-v1"),
                )
            }
        )
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/matching/telemetry", methods=["GET"])
def match_records_telemetry(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _auth(req)
        items = get_record_store().telemetry[-100:]
        return json_response({"items": items, "count": len(items)})
    except Exception as exc:
        return _handle(exc)


@bp.queue_trigger(arg_name="msg", queue_name="match-compute", connection="AzureWebJobsStorage")
def match_compute_job(msg: func.QueueMessage) -> None:
    get_service().process_compute(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)

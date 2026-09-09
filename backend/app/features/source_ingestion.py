"""Job Source Integration HTTP API, scheduler, and queue workers (Backend PRD)."""

from __future__ import annotations

import json

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.job_sources.errors import (
    JobSourceNotFoundError,
    JobSourceRateLimitedError,
    JobSourceValidationError,
)
from app.job_sources.runtime import get_service

bp = func.Blueprint()


def _auth(req: func.HttpRequest):
    return get_principal(req)


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, JobSourceValidationError):
        pointer = f"/{exc.path}" if exc.path else None
        return error_response(
            "VALIDATION_ERROR",
            str(exc),
            400,
            details=[{"path": pointer, "message": str(exc)}] if pointer else None,
        )
    if isinstance(exc, JobSourceNotFoundError):
        return error_response("NOT_FOUND", str(exc), 404)
    if isinstance(exc, JobSourceRateLimitedError):
        return error_response("RATE_LIMITED", str(exc), 429)
    raise exc


def _json_payload(msg: func.QueueMessage) -> dict:
    return json.loads(msg.get_body().decode("utf-8"))


@bp.route(route="v1/sources/{id}/crawl", methods=["POST"])
def start_crawl(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _auth(req)
        body = get_service().enqueue_crawl(req.route_params["id"])
        return json_response(body, status_code=202)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/sources/{id}/runs/{run_id}", methods=["GET"])
def get_crawl_run(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _auth(req)
        body = get_service().get_run(req.route_params["id"], req.route_params["run_id"])
        return json_response(body)
    except Exception as exc:
        return _handle(exc)


@bp.timer_trigger(schedule="0 */5 * * * *", arg_name="timer", run_on_startup=False)
def crawl_scheduler(timer: func.TimerRequest) -> None:
    get_service().schedule_due()


@bp.queue_trigger(arg_name="msg", queue_name="crawl-runs", connection="AzureWebJobsStorage")
def crawl_run_job(msg: func.QueueMessage) -> None:
    get_service().process_crawl_run(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)


@bp.queue_trigger(arg_name="msg", queue_name="job-fetch", connection="AzureWebJobsStorage")
def job_fetch_job(msg: func.QueueMessage) -> None:
    get_service().process_job_fetch(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)

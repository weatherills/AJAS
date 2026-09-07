"""Resume Management HTTP API and parse-queue worker (Backend PRD)."""

from __future__ import annotations

import json

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.resumes.errors import (
    FileRejectedError,
    ResumeNotFoundError,
    ResumeRateLimitedError,
    ResumeSelectionRejectedError,
    ResumeValidationError,
)
from app.resumes.mapping import resume_detail, resume_list_item, selection_api
from app.resumes.runtime import get_service

bp = func.Blueprint()


def _auth(req: func.HttpRequest):
    return get_principal(req)


def _handle_errors(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, ResumeNotFoundError):
        return error_response("NOT_FOUND", "Not found", 404)
    if isinstance(exc, FileRejectedError):
        return error_response(exc.code, str(exc), exc.status_code)
    if isinstance(exc, ResumeValidationError):
        pointer = f"/{exc.path}" if exc.path else None
        return error_response(
            "VALIDATION_ERROR",
            str(exc),
            400,
            details=[{"path": pointer, "message": str(exc)}] if pointer else None,
        )
    if isinstance(exc, ResumeSelectionRejectedError):
        return error_response("SELECTION_REJECTED", str(exc), 400)
    if isinstance(exc, ResumeRateLimitedError):
        return error_response("RATE_LIMITED", str(exc), 429)
    raise exc


@bp.route(route="resumes", methods=["POST"])
def upload_resume(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        filename, content_type, data = _read_upload(req)
        resume = get_service().upload(
            user_id=principal.user_id,
            filename=filename,
            content_type=content_type,
            data=data,
        )
        return json_response({"id": resume.id, "status": "uploaded"}, status_code=201)
    except Exception as exc:
        return _handle_errors(exc)


@bp.route(route="resumes", methods=["GET"])
def list_resumes(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        cursor = req.params.get("cursor")
        limit = int(req.params.get("limit") or 20)
        result = get_service().list_resumes(principal.user_id, cursor=cursor, limit=limit)
        return json_response(
            {
                "items": [resume_list_item(item) for item in result["items"]],
                "nextCursor": result["nextCursor"],
            }
        )
    except Exception as exc:
        return _handle_errors(exc)


@bp.route(route="resumes/{id}/preview-url", methods=["GET"])
def preview_url(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        url = get_service().preview_url(principal.user_id, req.route_params["id"])
        return json_response({"url": url, "expiresInSeconds": 600})
    except Exception as exc:
        return _handle_errors(exc)


@bp.route(route="resumes/{id}", methods=["GET"])
def get_resume(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        resume = get_service().get(principal.user_id, req.route_params["id"])
        return json_response(resume_detail(resume))
    except Exception as exc:
        return _handle_errors(exc)


@bp.route(route="resumes/{id}", methods=["PATCH"])
def patch_resume(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        try:
            body = req.get_json()
        except ValueError:
            return error_response("BAD_INPUT", "JSON body required", 400)
        if not isinstance(body, dict):
            return error_response("BAD_INPUT", "JSON object required", 400)
        resume = get_service().patch(principal.user_id, req.route_params["id"], body)
        return json_response(resume_detail(resume))
    except Exception as exc:
        return _handle_errors(exc)


@bp.route(route="resumes/{id}", methods=["DELETE"])
def delete_resume(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        get_service().delete(principal.user_id, req.route_params["id"])
        return func.HttpResponse(status_code=204)
    except Exception as exc:
        return _handle_errors(exc)


@bp.route(route="runs/{runId}/active-resume", methods=["POST"])
def set_active_resume(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        try:
            body = req.get_json()
        except ValueError:
            return error_response("BAD_INPUT", "JSON body required", 400)
        resume_id = (body or {}).get("resumeId")
        if not resume_id:
            return error_response("BAD_INPUT", "resumeId is required", 400)
        selection = get_service().set_active(
            principal.user_id, req.route_params["runId"], resume_id
        )
        return json_response(selection_api(selection))
    except Exception as exc:
        return _handle_errors(exc)


@bp.route(route="runs/{runId}/active-resume", methods=["GET"])
def get_active_resume(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        selection = get_service().get_active(principal.user_id, req.route_params["runId"])
        return json_response(selection_api(selection))
    except Exception as exc:
        return _handle_errors(exc)


@bp.queue_trigger(arg_name="msg", queue_name="resume-parse", connection="AzureWebJobsStorage")
def parse_resume_job(msg: func.QueueMessage) -> None:
    payload = json.loads(msg.get_body().decode("utf-8"))
    dequeue_count = msg.dequeue_count or 1
    get_service().process_parse_job(payload, dequeue_count=dequeue_count)


def _read_upload(req: func.HttpRequest) -> tuple[str, str | None, bytes]:
    files = req.files
    upload = files.get("file") if files else None
    if upload is None:
        raise FileRejectedError("Missing multipart field 'file'", status_code=400, code="MISSING_FILE")
    filename = getattr(upload, "filename", None) or "resume.bin"
    content_type = getattr(upload, "content_type", None)
    data = upload.read() if hasattr(upload, "read") else upload.stream.read()
    return filename, content_type, data

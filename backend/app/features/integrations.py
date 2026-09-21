"""Flag-gated product integrations HTTP API."""

from __future__ import annotations

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.integrations.service import get_service
from app.request_context import bind_request
from app.resumes.runtime import try_get_service as try_resume_service

bp = func.Blueprint()


def _auth(req: func.HttpRequest):
    return get_principal(req)


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    raise exc


def _json_body(req: func.HttpRequest) -> dict:
    try:
        body = req.get_json()
    except ValueError:
        return {}
    if body is None:
        return {}
    if not isinstance(body, dict):
        return {}
    return body


@bp.route(route="v1/integrations/status", methods=["GET"])
def integrations_status(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().status())
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/ingest/{source}", methods=["POST"])
def integrations_ingest(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        source = (req.route_params.get("source") or "").strip().lower()
        if source not in {"indeed", "linkedin"}:
            return error_response("VALIDATION_ERROR", "source must be indeed or linkedin", 400)
        body = _json_body(req)
        result = get_service().ingest(
            source,
            body.get("payload") or body,
            search=body.get("search"),
            listing_url=body.get("listingUrl"),
        )
        return json_response(result, status_code=202 if result.get("reason") == "ok" else 200)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/linkedin/search", methods=["GET"])
def integrations_search_inputs(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response({"search": get_service().search_spec(dict(req.params)), "supported": get_service().status()["searchInputs"]})
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/linkedin/easy-apply", methods=["POST"])
def integrations_easy_apply(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().easy_apply(_json_body(req)))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/linkedin/e2e", methods=["POST"])
def integrations_linkedin_e2e(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = _auth(req)
        body = _json_body(req)
        result = get_service().e2e(
            body.get("payload") or body,
            resume_text=str(body.get("resumeText") or "Staff python azure kubernetes engineer"),
            profile=dict(body.get("profile") or {"full_name": "Alex Jobseeker", "email": "alex@ajas.dev"}),
            decision=str(body.get("decision") or "approve"),
            search=body.get("search"),
        )
        result["userId"] = principal.user_id
        return json_response(result)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/greenhouse/applications", methods=["GET", "POST"])
def integrations_harvest(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        body = _json_body(req) if req.method.upper() == "POST" else {}
        email = req.params.get("email") or body.get("email")
        page = int(req.params.get("page") or body.get("page") or 1)
        pages = body.get("pages")
        return json_response(get_service().harvest(email=email, page=page, pages=pages))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/gmail/sync", methods=["POST"])
def integrations_gmail_sync(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = _auth(req)
        body = _json_body(req)
        return json_response(
            get_service().gmail_sync(
                principal.user_id,
                labels=list(body.get("labels") or ["INBOX"]),
                fixtures=body.get("messages") or body.get("fixtures"),
            )
        )
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/gmail/send", methods=["POST"])
def integrations_gmail_send(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = _auth(req)
        return json_response(get_service().gmail_send(principal.user_id, _json_body(req)))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/outlook/delta", methods=["GET"])
def integrations_outlook_delta(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = _auth(req)
        return json_response(get_service().outlook_delta(principal.user_id, req.params.get("token")))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/drive", methods=["GET"])
def integrations_drive_list(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = _auth(req)
        email = req.params.get("email") or f"{principal.user_id}@ajas.dev"
        return json_response(get_service().drive_list(email))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/drive/import", methods=["POST"])
def integrations_drive_import(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = _auth(req)
        body = _json_body(req)
        resume = try_resume_service()
        if resume is None:
            from app.resumes.service import ResumeService

            resume = ResumeService()
        return json_response(
            get_service().drive_import(
                user_id=principal.user_id,
                user_email=str(body.get("email") or f"{principal.user_id}@ajas.dev"),
                file_id=str(body.get("fileId") or ""),
                resume_service=resume,
            )
        )
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/slack/notify", methods=["POST"])
def integrations_slack(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        body = _json_body(req)
        return json_response(
            get_service().slack(
                kind=str(body.get("kind") or "match"),
                title=str(body.get("title") or "AJAS"),
                body=str(body.get("body") or ""),
            )
        )
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/linkedin/receipts", methods=["GET"])
def integrations_receipts(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().audit())
    except Exception as exc:
        return _handle(exc)

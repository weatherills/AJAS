"""Flag-gated product integrations HTTP API."""

from __future__ import annotations

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.integrations.ingest import HTTP_INGEST_SOURCES
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
        if source not in HTTP_INGEST_SOURCES:
            return error_response(
                "VALIDATION_ERROR",
                "source must be indeed, linkedin, glassdoor, workday, ziprecruiter, hired, or wellfound",
                400,
            )
        body = _json_body(req)
        payload = body.get("payload") if "payload" in body else body
        if not payload:
            raw = req.get_body() or b""
            if raw.lstrip().startswith(b"<"):
                payload = raw
        result = get_service().ingest(
            source,
            payload,
            search=body.get("search"),
            listing_url=body.get("listingUrl"),
            html=body.get("html"),
            live=bool(body.get("live")),
            account_id=str(body.get("accountId") or body.get("account_id") or "") or None,
        )
        return json_response(result, status_code=202 if result.get("reason") == "ok" else 200)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/linkedin/search", methods=["GET", "POST"])
def integrations_search_inputs(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        if req.method.upper() == "POST":
            body = _json_body(req)
            return json_response(get_service().linkedin_search(body))
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


@bp.route(route="v1/integrations/imap/sync", methods=["POST"])
def integrations_imap_sync(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = _auth(req)
        body = _json_body(req)
        payload = body.get("payload") if "payload" in body else None
        if not payload:
            raw = req.get_body() or b""
            if raw and (raw.lstrip().startswith(b"From:") or b"Message-ID:" in raw):
                payload = raw
        return json_response(
            get_service().imap_sync(
                principal.user_id,
                folder=body.get("folder"),
                since_uid=str(body.get("sinceUid") or body.get("cursor") or "") or None,
                fixtures=body.get("messages") or body.get("fixtures"),
                payload=payload,
                live=bool(body.get("live")),
            )
        )
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/imap/send", methods=["POST"])
def integrations_imap_send(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = _auth(req)
        return json_response(get_service().imap_send(principal.user_id, _json_body(req)))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/imap/spec", methods=["GET"])
def integrations_imap_spec(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().board_spec("imap"))
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


@bp.route(route="v1/integrations/indeed/spec", methods=["GET"])
def integrations_indeed_spec(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().board_spec("indeed"))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/glassdoor/spec", methods=["GET"])
def integrations_glassdoor_spec(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().board_spec("glassdoor"))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/workday/spec", methods=["GET"])
def integrations_workday_spec(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().board_spec("workday"))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/ziprecruiter/spec", methods=["GET"])
def integrations_ziprecruiter_spec(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().board_spec("ziprecruiter"))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/hired/spec", methods=["GET"])
def integrations_hired_spec(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().board_spec("hired"))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/wellfound/spec", methods=["GET"])
def integrations_wellfound_spec(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().board_spec("wellfound"))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/linkedin/spec", methods=["GET"])
def integrations_linkedin_spec(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        return json_response(get_service().linkedin_spec())
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/linkedin/session", methods=["GET", "POST"])
def integrations_linkedin_session(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        if req.method.upper() == "GET":
            return json_response(get_service().session_list())
        body = _json_body(req)
        account_id = str(body.get("accountId") or body.get("account_id") or "").strip()
        token = str(body.get("token") or "")
        if not account_id or not token:
            return error_response("VALIDATION_ERROR", "accountId and token are required", 400)
        ttl = body.get("ttlSeconds")
        return json_response(get_service().session_put(account_id, token, ttl_seconds=int(ttl) if ttl else None))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/linkedin/session/refresh", methods=["POST"])
def integrations_linkedin_session_refresh(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        body = _json_body(req)
        return json_response(
            get_service().session_refresh(str(body.get("accountId") or ""), body.get("token"))
        )
    except ValueError as exc:
        return error_response("VALIDATION_ERROR", str(exc), 400)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/integrations/linkedin/session/revoke", methods=["POST"])
def integrations_linkedin_session_revoke(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        _auth(req)
        body = _json_body(req)
        return json_response(get_service().session_revoke(str(body.get("accountId") or "")))
    except Exception as exc:
        return _handle(exc)

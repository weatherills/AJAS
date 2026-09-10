"""Email Ingestion & Reply HTTP API, Graph webhook, and ingest worker."""

from __future__ import annotations

import json

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.mail.errors import (
    MailConflictError,
    MailForbiddenError,
    MailNotFoundError,
    MailRateLimitedError,
    MailUnauthorizedError,
    MailUnprocessableError,
    MailValidationError,
)
from app.mail.runtime import get_service
from app.observability import log_exception, log_request

bp = func.Blueprint()


def _auth(req: func.HttpRequest):
    return get_principal(req)


def _handle(exc: Exception, *, route: str, method: str, user_id: str | None = None) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        log_request(feature="email", route=route, method=method, status=401, user_id=user_id, error=str(exc))
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, MailUnauthorizedError):
        log_request(feature="email", route=route, method=method, status=401, user_id=user_id, error=str(exc))
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, MailForbiddenError):
        log_request(feature="email", route=route, method=method, status=403, user_id=user_id, error=str(exc))
        return error_response("FORBIDDEN", str(exc), 403)
    if isinstance(exc, MailValidationError):
        pointer = f"/{exc.path}" if exc.path else None
        log_request(feature="email", route=route, method=method, status=400, user_id=user_id, error=str(exc))
        return error_response(
            "INVALID_INPUT",
            str(exc),
            400,
            details=[{"path": pointer, "message": str(exc)}] if pointer else None,
        )
    if isinstance(exc, MailUnprocessableError):
        log_request(feature="email", route=route, method=method, status=422, user_id=user_id, error=str(exc))
        return error_response("UNPROCESSABLE", str(exc), 422)
    if isinstance(exc, MailNotFoundError):
        log_request(feature="email", route=route, method=method, status=404, user_id=user_id, error=str(exc))
        return error_response("NOT_FOUND", str(exc), 404)
    if isinstance(exc, MailConflictError):
        log_request(feature="email", route=route, method=method, status=409, user_id=user_id, error=str(exc))
        return error_response("CONFLICT", str(exc), 409)
    if isinstance(exc, MailRateLimitedError):
        log_request(feature="email", route=route, method=method, status=429, user_id=user_id, error=str(exc))
        retry_after = int(getattr(exc, "retry_after", 86400) or 86400)
        return error_response(
            "RATE_LIMITED",
            str(exc),
            429,
            details={"retryAfter": retry_after},
            retry_after=retry_after,
        )
    log_exception("email", route, exc)
    raise exc


def _json_body(req: func.HttpRequest) -> dict:
    try:
        body = req.get_json()
    except ValueError as exc:
        raise MailValidationError("JSON body required") from exc
    if body is None:
        return {}
    if not isinstance(body, dict):
        raise MailValidationError("JSON object required")
    return body


def _query_int(value: str | None, path: str, *, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise MailValidationError(f"invalid {path}", path=path) from exc


def _json_payload(msg: func.QueueMessage) -> dict:
    return json.loads(msg.get_body().decode("utf-8"))


@bp.route(route="webhooks/graph/mail", methods=["GET", "POST"])
def graph_mail_webhook(req: func.HttpRequest) -> func.HttpResponse:
    try:
        token = req.params.get("validationToken") or req.params.get("validationtoken")
        payload = None
        if not token:
            try:
                payload = req.get_json()
            except ValueError:
                payload = {}
            if isinstance(payload, dict):
                token = payload.get("validationToken") or payload.get("validationtoken")
        status, body = get_service().handle_webhook(
            validation_token=token,
            payload=payload if isinstance(payload, dict) else None,
            client_state=req.headers.get("clientState"),
        )
        if isinstance(body, str):
            return func.HttpResponse(body, status_code=status, mimetype="text/plain")
        log_request(feature="email", route="webhooks/graph/mail", method=req.method, status=status)
        return json_response(body, status_code=status)
    except Exception as exc:
        return _handle(exc, route="webhooks/graph/mail", method=req.method)


@bp.route(route="v1/email/status", methods=["GET"])
def email_status(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().status(principal.user_id)
        log_request(feature="email", route="v1/email/status", method="GET", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/email/status", method="GET")


@bp.route(route="v1/email/threads", methods=["GET"])
def list_email_threads(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().list_threads(
            principal.user_id,
            job_id=req.params.get("jobId") or None,
            unlinked_only=(req.params.get("unlinked") or "").lower() in {"1", "true", "yes"},
            limit=_query_int(req.params.get("limit"), "limit", default=50),
            cursor=req.params.get("cursor") or None,
        )
        log_request(feature="email", route="v1/email/threads", method="GET", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/email/threads", method="GET")


@bp.route(route="v1/email/refresh", methods=["POST"])
def refresh_email(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().refresh(principal.user_id)
        log_request(feature="email", route="v1/email/refresh", method="POST", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/email/refresh", method="POST")


@bp.route(route="v1/email/templates", methods=["GET"])
def list_email_templates(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().templates()
        log_request(feature="email", route="v1/email/templates", method="GET", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/email/templates", method="GET")


@bp.route(route="v1/email/templates/{templateId}/preview", methods=["GET"])
def preview_email_template(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        from app.mail.keys import apply_template
        from app.mail.theme import THEME, render_html

        template_id = req.route_params["templateId"]
        template = next((item for item in get_service().templates()["items"] if item["id"] == template_id), None)
        if template is None:
            from app.mail.errors import MailNotFoundError

            raise MailNotFoundError(template_id)
        variables = {
            "firstName": req.params.get("firstName") or "Alex",
            "company": req.params.get("company") or "Acme",
            "role": req.params.get("role") or "Engineer",
            "jobRef": req.params.get("jobRef") or "JOB-1",
        }
        text = apply_template(template["body"], variables)
        html = render_html(text, name=template["name"])
        log_request(feature="email", route="v1/email/templates/preview", method="GET", status=200, user_id=principal.user_id)
        return json_response({"id": template_id, "name": template["name"], "text": text, "html": html, "theme": THEME})
    except Exception as exc:
        return _handle(exc, route="v1/email/templates/preview", method="GET")


@bp.route(route="v1/email/webhooks/bounce", methods=["POST"])
def email_bounce_webhook(req: func.HttpRequest) -> func.HttpResponse:
    try:
        from app.mail.bounce import classify_delivery
        from app.mail import suppression

        payload = {}
        try:
            payload = req.get_json() or {}
        except ValueError:
            payload = {}
        address = str(payload.get("email") or payload.get("address") or payload.get("recipient") or "")
        reason = str(payload.get("type") or payload.get("reason") or "bounce").lower()
        if reason not in {"bounce", "bounced", "complaint", "complained"}:
            kind = classify_delivery(payload.get("from") or "", payload.get("subject") or "", payload.get("body") or "")
            reason = kind or "bounce"
        if reason in {"complaint", "complained"}:
            reason = "complaint"
        else:
            reason = "bounce"
        row = suppression.suppress(address, reason=reason, source="webhook")
        return json_response({"suppressed": True, **row}, status_code=202)
    except ValueError as exc:
        return error_response("INVALID_INPUT", str(exc), 400)
    except Exception as exc:
        return _handle(exc, route="v1/email/webhooks/bounce", method="POST")


@bp.route(route="v1/email/suppressions", methods=["GET"])
def list_email_suppressions(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        from app.mail import suppression

        log_request(feature="email", route="v1/email/suppressions", method="GET", status=200, user_id=principal.user_id)
        return json_response({"items": suppression.list_all()})
    except Exception as exc:
        return _handle(exc, route="v1/email/suppressions", method="GET")


@bp.route(route="v1/jobs/{jobId}/threads", methods=["GET"])
def list_job_email_threads(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().list_threads(
            principal.user_id,
            job_id=req.route_params["jobId"],
            limit=_query_int(req.params.get("limit"), "limit", default=50),
            cursor=req.params.get("cursor") or None,
        )
        log_request(feature="email", route="v1/jobs/{jobId}/threads", method="GET", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/jobs/{jobId}/threads", method="GET")


@bp.route(route="v1/threads/{threadId}/messages", methods=["GET"])
def list_thread_messages(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().list_messages(
            principal.user_id,
            req.route_params["threadId"],
            limit=_query_int(req.params.get("limit"), "limit", default=50),
            cursor=req.params.get("cursor") or None,
        )
        log_request(feature="email", route="v1/threads/{threadId}/messages", method="GET", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/threads/{threadId}/messages", method="GET")


@bp.route(route="v1/threads/{threadId}/reply", methods=["POST"])
def reply_thread(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        status, body = get_service().reply(principal.user_id, req.route_params["threadId"], _json_body(req))
        log_request(feature="email", route="v1/threads/{threadId}/reply", method="POST", status=status, user_id=principal.user_id)
        return json_response(body, status_code=status)
    except Exception as exc:
        return _handle(exc, route="v1/threads/{threadId}/reply", method="POST")


@bp.route(route="v1/threads/{threadId}/suggestions", methods=["POST"])
def suggest_thread_replies(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().suggestions(principal.user_id, req.route_params["threadId"], _json_body(req))
        log_request(feature="email", route="v1/threads/{threadId}/suggestions", method="POST", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/threads/{threadId}/suggestions", method="POST")


@bp.route(route="v1/threads/{threadId}/link", methods=["POST"])
def link_email_thread(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().link(principal.user_id, req.route_params["threadId"], _json_body(req))
        log_request(feature="email", route="v1/threads/{threadId}/link", method="POST", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/threads/{threadId}/link", method="POST")


@bp.route(route="v1/threads/{threadId}/unlink", methods=["POST"])
def unlink_email_thread(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = _auth(req)
        body = get_service().unlink(principal.user_id, req.route_params["threadId"])
        log_request(feature="email", route="v1/threads/{threadId}/unlink", method="POST", status=200, user_id=principal.user_id)
        return json_response(body)
    except Exception as exc:
        return _handle(exc, route="v1/threads/{threadId}/unlink", method="POST")


@bp.queue_trigger(arg_name="msg", queue_name="mail-ingest", connection="AzureWebJobsStorage")
def mail_ingest_job(msg: func.QueueMessage) -> None:
    get_service().process_ingest(_json_payload(msg), dequeue_count=msg.dequeue_count or 1)


@bp.timer_trigger(schedule="0 */10 * * * *", arg_name="timer", run_on_startup=False)
def mail_poll_timer(timer: func.TimerRequest) -> None:
    get_service().poll_all()


@bp.timer_trigger(schedule="0 0 3 * * *", arg_name="timer", run_on_startup=False)
def mail_retention_timer(timer: func.TimerRequest) -> None:
    get_service().purge_expired()

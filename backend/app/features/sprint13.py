"""Sprint 13 HTTP surface: chaos, canary, traces, audit, redaction, search."""

from __future__ import annotations

import json

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.request_context import bind_request
from app.sprint12.security import SECURITY_HEADERS
from app.sprint13 import VERSION

bp = func.Blueprint()


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, PermissionError):
        return error_response("FORBIDDEN", str(exc), 403)
    if isinstance(exc, (ValueError, KeyError)):
        return error_response("BAD_REQUEST", str(exc), 400)
    raise exc


def _body(req: func.HttpRequest) -> dict:
    if not req.get_body():
        return {}
    try:
        return json.loads(req.get_body())
    except json.JSONDecodeError:
        return {}


def _ok(payload) -> func.HttpResponse:
    headers = dict(SECURITY_HEADERS)
    headers["X-AJAS-Sprint"] = VERSION
    return json_response(payload, headers=headers)


@bp.route(route="v1/s13/status", methods=["GET", "OPTIONS"])
def status(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    if req.method.upper() == "OPTIONS":
        return json_response({"ok": True})
    from app.sprint13 import COMPLETED

    return _ok({"version": VERSION, "completed": COMPLETED})


@bp.route(route="v1/s13/kill", methods=["GET", "POST"])
def kill(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        get_principal(req)
        from app.sprint13.platform import inject_failure, kill_switch

        if req.method.upper() == "GET":
            name = req.params.get("name") or "ingest"
            return _ok(kill_switch(name))
        body = _body(req)
        name = body.get("name") or "ingest"
        if body.get("inject"):
            return _ok(inject_failure(name))
        return _ok(kill_switch(name, enabled=bool(body.get("enabled"))))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/s13/canary", methods=["POST"])
def canary(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = get_principal(req)
        from app.sprint13.platform import canary as set_canary, canary_assign

        body = _body(req)
        cfg = set_canary(flag=body.get("flag") or "fit-v2", percent=int(body.get("percent") or 0), env=body.get("env") or "prod")
        cfg["bucket"] = canary_assign(cfg["flag"], principal.user_id)
        return _ok(cfg)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/s13/e2e", methods=["GET"])
def e2e(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        get_principal(req)
        from app.sprint13.platform import e2e_happy_path, e2e_retry_path

        if (req.params.get("mode") or "happy") == "retry":
            return _ok(e2e_retry_path(fail_at=req.params.get("failAt") or "apply"))
        return _ok(e2e_happy_path())
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/s13/traces", methods=["GET"])
def traces(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        get_principal(req)
        from app.sprint13.ops import trace_viewer

        return _ok(trace_viewer(trace_id=req.params.get("traceId")))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/s13/audit", methods=["GET"])
def audit(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        get_principal(req)
        from app.sprint13.ops import audit_bundle

        bundle = audit_bundle()
        fmt = (req.params.get("format") or "json").lower()
        if fmt == "csv":
            return func.HttpResponse(bundle["csv"], mimetype="text/csv", status_code=200)
        return _ok(bundle)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/s13/redact", methods=["POST"])
def redact(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = get_principal(req)
        from app.sprint13.security import apply_field_redaction, set_field_redaction

        body = _body(req)
        tenant = body.get("tenantId") or principal.user_id
        if "fields" in body:
            set_field_redaction(tenant, list(body.get("fields") or []))
        payload = body.get("payload") or {}
        return _ok(apply_field_redaction(tenant, payload))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/s13/search", methods=["GET"])
def search(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        get_principal(req)
        from app.sprint13.platform import api_query

        raw = req.params.get("items")
        items = json.loads(raw) if raw else []
        filters = {}
        company = req.params.get("company")
        if company:
            filters["company"] = company
        return _ok(
            api_query(
                items,
                q=req.params.get("q"),
                sort=req.params.get("sort") or "id",
                order=req.params.get("order") or "asc",
                filters=filters or None,
            )
        )
    except Exception as exc:
        return _handle(exc)

"""Sprint 14 HTTP surface."""

from __future__ import annotations

import json

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.request_context import bind_request
from app.sprint12.security import SECURITY_HEADERS
from app.sprint14 import VERSION

bp = func.Blueprint()


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, (ValueError, KeyError)):
        return error_response("BAD_REQUEST", str(exc), 400)
    raise exc


def _ok(payload) -> func.HttpResponse:
    headers = dict(SECURITY_HEADERS)
    headers["X-AJAS-Sprint"] = VERSION
    return json_response(payload, headers=headers)


@bp.route(route="v1/s14/status", methods=["GET", "OPTIONS"])
def s14_status(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    if req.method.upper() == "OPTIONS":
        return json_response({"ok": True})
    from app.sprint14 import COMPLETED

    return _ok({"version": VERSION, "completed": COMPLETED})


@bp.route(route="v1/s14/health", methods=["GET"])
def s14_health(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    from app.sprint14.ops import health_matrix

    return _ok(health_matrix())


@bp.route(route="v1/s14/search", methods=["GET"])
def s14_search(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        get_principal(req)
        from app.sprint14.product import search_jd

        raw = req.params.get("items")
        items = json.loads(raw) if raw else []
        return _ok(search_jd(items, req.params.get("q") or ""))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/s14/traces", methods=["GET"])
def s14_traces(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        get_principal(req)
        from app.sprint14.ops import traces as traces_mod

        return _ok(traces_mod("match", trace_id=req.params.get("traceId") or "s14"))
    except Exception as exc:
        return _handle(exc)

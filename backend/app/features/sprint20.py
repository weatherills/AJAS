"""Sprint 20 HTTP surface."""

from __future__ import annotations

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.request_context import bind_request
from app.sprint12.security import SECURITY_HEADERS
from app.sprint20 import VERSION

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


@bp.route(route="v1/s20/status", methods=["GET", "OPTIONS"])
def s20_status(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    if req.method.upper() == "OPTIONS":
        return json_response({"ok": True})
    from app.sprint20 import COMPLETED

    return _ok({"version": VERSION, "completed": COMPLETED})


@bp.route(route="v1/s20/health", methods=["GET"])
def s20_health(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    from app.sprint20.ops import health_v9

    return _ok(health_v9())


@bp.route(route="v1/s20/kanban", methods=["GET"])
def s20_kanban(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    from app.sprint20.kanban import status as kanban_status

    return _ok(kanban_status())


@bp.route(route="v1/s20/traces", methods=["GET"])
def s20_traces(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        get_principal(req)
        from app.sprint20.ops import traces_s20

        return _ok(traces_s20("match", trace_id=req.params.get("traceId") or "s20"))
    except Exception as exc:
        return _handle(exc)

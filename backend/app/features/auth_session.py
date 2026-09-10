"""Session issue / refresh / device list (Sprint 6 session hardening)."""

from __future__ import annotations

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.rbac import role_for_principal
from app.sessions import create_session, list_devices, rotate_refresh, revoke_device

bp = func.Blueprint()


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, ValueError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    if isinstance(exc, KeyError):
        return error_response("NOT_FOUND", "device not found", 404)
    raise exc


def _client_meta(req: func.HttpRequest) -> tuple[str, str | None]:
    agent = req.headers.get("User-Agent") or req.headers.get("user-agent") or ""
    forwarded = req.headers.get("X-Forwarded-For") or req.headers.get("x-forwarded-for") or ""
    ip = forwarded.split(",")[0].strip() or None
    return agent, ip


@bp.route(route="v1/auth/session", methods=["POST"])
def create_auth_session(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = get_principal(req)
        agent, ip = _client_meta(req)
        body = {}
        try:
            body = req.get_json() or {}
        except ValueError:
            body = {}
        label = str(body.get("label") or "This device")
        issued = create_session(
            principal.user_id,
            role=role_for_principal(principal),
            label=label,
            user_agent=agent,
            ip=ip,
        )
        return json_response(issued, status_code=201)
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/auth/refresh", methods=["POST"])
def refresh_auth_session(req: func.HttpRequest) -> func.HttpResponse:
    try:
        try:
            body = req.get_json() or {}
        except ValueError:
            body = {}
        token = str(body.get("refreshToken") or body.get("refresh_token") or "")
        agent, ip = _client_meta(req)
        return json_response(rotate_refresh(token, user_agent=agent, ip=ip))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/auth/devices", methods=["GET"])
def list_auth_devices(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = get_principal(req)
        return json_response({"items": list_devices(principal.user_id)})
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/auth/devices/{deviceId}", methods=["DELETE"])
def delete_auth_device(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = get_principal(req)
        revoke_device(principal.user_id, req.route_params["deviceId"])
        return json_response({"revoked": True})
    except Exception as exc:
        return _handle(exc)

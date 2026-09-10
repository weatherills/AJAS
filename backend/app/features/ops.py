"""Ops: traces, SLO, seed, pagination contract, ingestion metrics."""

from __future__ import annotations

import azure.functions as func

from app.auth import AuthError, get_principal
from app.config import get_settings, microsoft_oauth_configured
from app.http import error_response, json_response
from app.ingestion_alerts import maybe_alert
from app.job_sources.global_limit import snapshot as global_limit_snapshot
from app.job_sources.runtime import try_get_service as try_job_source_service
from app.pagination import DEFAULT_LIMIT, MAX_LIMIT, MIN_LIMIT
from app.rbac import permissions_payload, require_role
from app.request_context import bind_request
from app.tracing import snapshot as trace_snapshot

bp = func.Blueprint()


def _handle(exc: Exception) -> func.HttpResponse:
    if isinstance(exc, AuthError):
        return error_response("UNAUTHENTICATED", str(exc), 401)
    from app.auth import ForbiddenError

    if isinstance(exc, ForbiddenError):
        return error_response("FORBIDDEN", str(exc), 403)
    raise exc


@bp.route(route="v1/ops/traces", methods=["GET"])
def ops_traces(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = get_principal(req)
        require_role(principal, "admin")
        return json_response(trace_snapshot())
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/ops/ingestion", methods=["GET"])
def ops_ingestion(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = get_principal(req)
        require_role(principal, "admin")
        service = try_job_source_service()
        event_log = getattr(service, "events", None) if service is not None else None
        events = list(getattr(event_log, "events", []) or [])[-50:]
        failures = sum(1 for item in events if item.get("kind") in {"error", "rate_limited"})
        alerted = maybe_alert(failure_count=failures, events=events)
        return json_response(
            {
                "events": events[-20:],
                "failureCount": failures,
                "globalRateLimit": global_limit_snapshot(),
                "alert": alerted or failures >= 3,
            }
        )
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/ops/seed", methods=["POST"])
def ops_seed(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = get_principal(req)
        from app.learning.runtime import get_service as get_learning
        from app.settings.runtime import get_service as get_settings_svc

        get_settings_svc().get(principal.user_id)
        get_learning().metrics(principal.user_id)
        return json_response(
            {
                "seeded": True,
                "userId": principal.user_id,
                "note": "In-memory demo stores populate on first read. Restarting Functions clears them.",
            }
        )
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/meta/pagination", methods=["GET"])
def pagination_contract(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    return json_response(
        {
            "limitParam": "limit",
            "aliases": {"pageSize": "limit", "continuation": "cursor"},
            "cursorParam": "cursor",
            "defaultLimit": DEFAULT_LIMIT,
            "minLimit": MIN_LIMIT,
            "maxLimit": MAX_LIMIT,
            "nextCursorField": "nextCursor",
            "reviewAlias": "continuationToken",
        }
    )


@bp.route(route="v1/auth/me", methods=["GET"])
def auth_me(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = get_principal(req)
        return json_response(permissions_payload(principal))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/auth/config", methods=["GET", "OPTIONS"])
def auth_config(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    if req.method.upper() == "OPTIONS":
        return json_response({"ok": True})
    settings = get_settings()
    mode = (settings.auth_mode or "dev").lower()
    client_id = (settings.microsoft_client_id or "").strip()
    tenant = (settings.microsoft_tenant or "common").strip() or "common"
    login_url = None
    if mode == "aad" and client_id:
        login_url = (
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
            f"?client_id={client_id}&response_type=token&response_mode=fragment"
            "&scope=openid%20profile%20offline_access&state=ajas"
        )
    return json_response(
        {
            "mode": mode,
            "loginUrl": login_url,
            "configured": mode != "aad" or bool(settings.auth_jwt_secret or settings.auth_jwt_jwks_url),
            "oauthConfigured": microsoft_oauth_configured(settings),
            "sessionCookies": bool(settings.auth_session_cookies),
        }
    )

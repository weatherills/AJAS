"""Sprint 12 HTTP surface: tenancy, billing, sharing, admin, legal, keys."""

from __future__ import annotations

import json

import azure.functions as func

from app.auth import AuthError, get_principal
from app.http import error_response, json_response
from app.request_context import bind_request
from app.sprint12 import VERSION
from app.sprint12 import billing as billing_mod
from app.sprint12 import ops as ops_mod
from app.sprint12 import platform as platform_mod
from app.sprint12 import ranking as ranking_mod
from app.sprint12 import sharing as sharing_mod
from app.sprint12 import tenants as tenants_mod
from app.sprint12.security import SECURITY_HEADERS

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


def _ok(payload, *, tenant: str = "anon", endpoint: str = "*") -> func.HttpResponse:
    headers = dict(SECURITY_HEADERS)
    headers.update(platform_mod.rate_headers(tenant, endpoint))
    return json_response(payload, headers=headers)


@bp.route(route="v1/tenants", methods=["GET", "POST", "OPTIONS"])
def tenants(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    if req.method.upper() == "OPTIONS":
        return json_response({"ok": True})
    try:
        principal = get_principal(req)
        if req.method.upper() == "GET":
            return _ok({"items": tenants_mod.list_tenants_for(principal.user_id)}, tenant=principal.user_id, endpoint="tenants")
        body = _body(req)
        tenant = tenants_mod.create_tenant(name=body.get("name") or "Workspace", owner_id=principal.user_id)
        billing_mod.assign_plan(tenant.id, "free")
        return _ok({"id": tenant.id, "name": tenant.name, "slug": tenant.slug}, tenant=tenant.id, endpoint="tenants")
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/tenants/{tenantId}/invites", methods=["POST"])
def tenant_invites(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = get_principal(req)
        tenant_id = req.route_params.get("tenantId") or ""
        body = _body(req)
        invite = tenants_mod.invite_member(
            tenant_id=tenant_id,
            actor_id=principal.user_id,
            email=body.get("email") or "",
            role=body.get("role") or "member",
        )
        return _ok({"id": invite.id, "email": invite.email, "role": invite.role, "token": invite.token}, tenant=tenant_id, endpoint="invites")
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/billing/usage", methods=["GET"])
def billing_usage(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = get_principal(req)
        tenant_id = req.params.get("tenantId") or principal.user_id
        return _ok(
            {"plan": billing_mod.plan_of(tenant_id), "usage": billing_mod.usage_of(tenant_id), "invoices": billing_mod.invoices_for(tenant_id)},
            tenant=tenant_id,
            endpoint="billing",
        )
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/billing/stripe/webhook", methods=["POST"])
def stripe_webhook(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        return _ok(billing_mod.handle_stripe_webhook(_body(req)), endpoint="stripe")
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/share/links", methods=["POST"])
def share_links(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = get_principal(req)
        body = _body(req)
        row = sharing_mod.create_link(
            tenant_id=body.get("tenantId") or principal.user_id,
            actor_id=principal.user_id,
            target_type=body.get("targetType") or "job",
            target_id=body.get("targetId") or "",
            ttl_hours=int(body.get("ttlHours") or 72),
        )
        return _ok(row, tenant=row["tenantId"], endpoint="share")
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/share/{token}", methods=["GET", "OPTIONS"])
def share_get(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    if req.method.upper() == "OPTIONS":
        return json_response({"ok": True})
    try:
        token = req.route_params.get("token") or ""
        return _ok(sharing_mod.recruiter_view(token))
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/admin/overview", methods=["GET"])
def admin_overview(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = get_principal(req)
        from app.rbac import require_role

        require_role(principal, "admin", "owner")
        return _ok(ops_mod.health_overview(storage="memory", workers={"match": True, "ingest": True}), tenant=principal.user_id, endpoint="admin")
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/feedback/matches/{jobId}", methods=["POST"])
def match_feedback(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = get_principal(req)
        body = _body(req)
        row = ranking_mod.record_feedback(
            user_id=principal.user_id,
            job_id=req.route_params.get("jobId") or "",
            vote=body.get("vote") or "",
            reason=body.get("reason"),
        )
        return _ok({"feedback": row, "weights": ranking_mod.weights_for(principal.user_id)}, tenant=principal.user_id, endpoint="feedback")
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/legal", methods=["GET", "OPTIONS"])
def legal(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    return _ok(platform_mod.legal_bundle())


@bp.route(route="v1/changelog", methods=["GET", "OPTIONS"])
def changelog(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    return _ok({"items": platform_mod.CHANGELOG, "version": VERSION})


@bp.route(route="v1/api-keys", methods=["GET", "POST"])
def api_keys(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    try:
        principal = get_principal(req)
        if req.method.upper() == "GET":
            return _ok({"items": platform_mod.list_api_keys(principal.user_id)}, tenant=principal.user_id, endpoint="api-keys")
        body = _body(req)
        row = platform_mod.create_api_key(user_id=principal.user_id, name=body.get("name") or "default", scopes=body.get("scopes") or ["read"])
        return _ok(row, tenant=principal.user_id, endpoint="api-keys")
    except Exception as exc:
        return _handle(exc)


@bp.route(route="v1/help", methods=["GET", "OPTIONS"])
def help_docs(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    q = req.params.get("q") or ""
    items = platform_mod.search_docs(q) if q else platform_mod.knowledge_base()
    return _ok({"items": items})

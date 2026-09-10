"""Health/liveness endpoint (infrastructure, not a product feature)."""
import azure.functions as func

from app.config import get_settings
from app.http import json_response
from app.request_context import bind_request

bp = func.Blueprint()

LIVE_FEATURES = ["health", "review", "auto-apply", "settings", "resume", "jobs", "matching", "email", "learning"]


def _status_payload() -> dict:
    settings = get_settings()
    storage = "cosmos" if settings.cosmos_connection_string else "memory"
    return {
        "status": "ok",
        "service": "ajas-backend",
        "authMode": settings.auth_mode or "dev",
        "storage": storage,
        "features": LIVE_FEATURES,
    }


@bp.route(route="health", methods=["GET", "OPTIONS"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    if req.method.upper() == "OPTIONS":
        return json_response({"ok": True})
    return json_response(_status_payload())


@bp.route(route="ready", methods=["GET", "OPTIONS"])
def ready(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    if req.method.upper() == "OPTIONS":
        return json_response({"ok": True})
    body = _status_payload()
    body["ready"] = True
    return json_response(body)


@bp.route(route="{*path}", methods=["OPTIONS"])
def cors_preflight(req: func.HttpRequest) -> func.HttpResponse:
    bind_request(req)
    return json_response({"ok": True})

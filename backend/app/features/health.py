"""Health/liveness endpoint (infrastructure, not a product feature)."""
import azure.functions as func

from app.config import get_settings
from app.http import json_response

bp = func.Blueprint()

LIVE_FEATURES = ["health", "review", "auto-apply", "settings", "resume", "jobs", "matching"]


@bp.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    settings = get_settings()
    storage = "cosmos" if settings.cosmos_connection_string else "memory"
    return json_response(
        {
            "status": "ok",
            "service": "ajas-backend",
            "authMode": settings.auth_mode or "dev",
            "storage": storage,
            "features": LIVE_FEATURES,
        }
    )

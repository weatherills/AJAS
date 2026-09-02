"""Health/liveness endpoint (infrastructure, not a product feature)."""
import azure.functions as func

from app.http import json_response

bp = func.Blueprint()


@bp.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    return json_response({"status": "ok", "service": "ajas-backend"})

"""CORS allowlist. Localhost is always allowed in AUTH_MODE=dev."""

from __future__ import annotations

import azure.functions as func

from app.config import get_settings


def allowed_origins() -> list[str]:
    settings = get_settings()
    raw = (settings.cors_allowed_origins or "").strip()
    origins = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    mode = (settings.auth_mode or "dev").lower()
    if mode == "dev":
        for local in ("http://localhost:3000", "http://127.0.0.1:3000"):
            if local not in origins:
                origins.append(local)
    return origins


def cors_headers(req: func.HttpRequest | None = None) -> dict[str, str]:
    origin = ""
    if req is not None:
        origin = (req.headers.get("Origin") or req.headers.get("origin") or "").rstrip("/")
    allow = allowed_origins()
    chosen = origin if origin in allow else (allow[0] if allow else "*")
    headers = {
        "Access-Control-Allow-Origin": chosen,
        "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Request-Id, X-User-Id, X-Role, X-CSRF-Token, X-Webhook-Secret, Idempotency-Key, If-Match",
        "Access-Control-Allow-Methods": "GET, POST, PATCH, PUT, DELETE, OPTIONS",
        "Access-Control-Expose-Headers": "X-Request-Id, X-CSRF-Token, Retry-After",
        "Access-Control-Max-Age": "600",
    }
    if chosen != "*":
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Vary"] = "Origin"
    return headers

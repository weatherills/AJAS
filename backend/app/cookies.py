"""HttpOnly session cookie packing plus CSRF token for cookie-authenticated writes."""

from __future__ import annotations

import base64
import json
import secrets
from typing import Any

import azure.functions as func

COOKIE_NAME = "ajas_sess"
CSRF_HEADER = "X-CSRF-Token"


def pack_session_cookie(access: str, refresh: str, *, max_age: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"at": access, "rt": refresh}).encode("utf-8")).decode("ascii")
    return f"{COOKIE_NAME}={payload}; HttpOnly; Path=/; SameSite=Lax; Max-Age={int(max_age)}"


def unpack_session_cookie(req: func.HttpRequest) -> dict[str, str] | None:
    raw = req.headers.get("Cookie") or req.headers.get("cookie") or ""
    token = ""
    for part in raw.split(";"):
        piece = part.strip()
        if piece.startswith(f"{COOKIE_NAME}="):
            token = piece.split("=", 1)[1].strip()
            break
    if not token:
        return None
    try:
        padding = "=" * (-len(token) % 4)
        body = json.loads(base64.urlsafe_b64decode(token + padding).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(body, dict):
        return None
    access = str(body.get("at") or "")
    refresh = str(body.get("rt") or "")
    if not access:
        return None
    return {"at": access, "rt": refresh}


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def require_csrf(req: func.HttpRequest, expected: str | None) -> None:
    if req.method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return
    header = (req.headers.get(CSRF_HEADER) or req.headers.get("x-csrf-token") or "").strip()
    if not expected or not header or header != expected:
        from app.auth import AuthError

        raise AuthError("CSRF token missing or invalid")


def cookie_headers(issued: dict[str, Any], *, csrf: str) -> dict[str, str]:
    from app.sessions import REFRESH_TTL_SECONDS

    return {
        "Set-Cookie": pack_session_cookie(issued["accessToken"], issued["refreshToken"], max_age=REFRESH_TTL_SECONDS),
        "X-CSRF-Token": csrf,
    }

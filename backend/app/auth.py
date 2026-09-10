"""Authentication for feature endpoints.

``AUTH_MODE=dev`` (default): ``Authorization: Bearer <user_id>`` or ``X-User-Id``.
Optional ``X-Scopes`` (space-separated) defaults to ``read:review write:review``.

``AUTH_MODE=aad``: validate a JWT and take ``oid`` (fallback ``sub``) as the user id.
Scopes come from the ``scp`` claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import azure.functions as func

from app.config import get_settings
from app.auto_apply.constants import READ_SCOPE as AUTO_APPLY_READ, WRITE_SCOPE as AUTO_APPLY_WRITE
from app.request_context import bind_request, set_user_id
from app.review.constants import READ_SCOPE, WRITE_SCOPE
from app.sessions import PREFIX as SESSION_PREFIX, parse_access_token

DEV_SCOPES = frozenset({READ_SCOPE, WRITE_SCOPE, AUTO_APPLY_READ, AUTO_APPLY_WRITE})


class AuthError(Exception):
    """Raised when a request is unauthenticated or unauthorized."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message)


class ForbiddenError(Exception):
    """Raised when the caller is authenticated but missing a required scope."""

    def __init__(self, message: str = "Missing required scope"):
        super().__init__(message)


@dataclass(frozen=True)
class Principal:
    """The authenticated caller."""

    user_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)


def get_principal(req: func.HttpRequest) -> Principal:
    """Resolve the authenticated principal from a request."""
    bind_request(req)
    settings = get_settings()
    header = req.headers.get("Authorization") or req.headers.get("authorization") or ""
    token = ""
    if header.lower().startswith("bearer "):
        token = header[7:].strip()

    mode = (settings.auth_mode or "dev").lower()
    if mode == "dev":
        if token.startswith(SESSION_PREFIX):
            session = parse_access_token(token)
            if not session:
                raise AuthError("Session expired")
            user_id, role = session
        else:
            user_id = token or (req.headers.get("X-User-Id") or req.headers.get("x-user-id") or "").strip()
            role = (req.headers.get("X-Role") or req.headers.get("x-role") or "").strip().lower()
        if not user_id:
            raise AuthError("Authentication required")
        raw_scopes = (req.headers.get("X-Scopes") or req.headers.get("x-scopes") or "").strip()
        if raw_scopes:
            scopes = frozenset(raw_scopes.split())
        elif role == "admin" or user_id in {"admin", "local-admin"}:
            scopes = DEV_SCOPES | frozenset({"admin", "read:ops", "write:ops"})
        else:
            scopes = DEV_SCOPES
        set_user_id(user_id)
        return Principal(user_id=user_id, scopes=scopes)

    if mode == "aad":
        if not token:
            raise AuthError("Authentication required")
        return _principal_from_aad_jwt(token, settings)

    raise AuthError(f"Unsupported AUTH_MODE {settings.auth_mode!r}")


def require_scopes(principal: Principal, *needed: str) -> None:
    missing = [scope for scope in needed if scope not in principal.scopes]
    if missing:
        raise ForbiddenError(f"Missing required scope: {' '.join(missing)}")


def _principal_from_aad_jwt(token: str, settings) -> Principal:
    import jwt

    if not settings.auth_jwt_secret and not settings.auth_jwt_jwks_url:
        raise AuthError("AAD auth is not configured")
    options = {"verify_aud": bool(settings.auth_jwt_audience)}
    kwargs: dict = {"algorithms": ["RS256", "HS256"], "options": options}
    if settings.auth_jwt_audience:
        kwargs["audience"] = settings.auth_jwt_audience
    if settings.auth_jwt_jwks_url:
        from jwt import PyJWKClient

        signing_key = PyJWKClient(settings.auth_jwt_jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(token, signing_key.key, **kwargs)
    else:
        payload = jwt.decode(token, settings.auth_jwt_secret, **kwargs)
    user_id = payload.get("oid") or payload.get("sub")
    if not user_id:
        raise AuthError("Token is missing oid/sub")
    scp = payload.get("scp") or payload.get("scope") or ""
    scopes = frozenset(str(scp).split()) if scp else frozenset()
    set_user_id(str(user_id))
    return Principal(user_id=str(user_id), scopes=scopes)

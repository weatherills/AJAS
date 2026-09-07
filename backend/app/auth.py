"""Authentication for feature endpoints.

``AUTH_MODE=dev`` (default): ``Authorization: Bearer <user_id>`` or ``X-User-Id``.
``AUTH_MODE=aad``: validate a JWT and take ``oid`` (fallback ``sub``) as the user id.
"""
from __future__ import annotations

from dataclasses import dataclass

import azure.functions as func

from app.config import get_settings


class AuthError(Exception):
    """Raised when a request is unauthenticated or unauthorized."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message)


@dataclass(frozen=True)
class Principal:
    """The authenticated caller."""

    user_id: str


def get_principal(req: func.HttpRequest) -> Principal:
    """Resolve the authenticated principal from a request."""
    settings = get_settings()
    header = req.headers.get("Authorization") or req.headers.get("authorization") or ""
    token = ""
    if header.lower().startswith("bearer "):
        token = header[7:].strip()

    mode = (settings.auth_mode or "dev").lower()
    if mode == "dev":
        user_id = token or (req.headers.get("X-User-Id") or req.headers.get("x-user-id") or "").strip()
        if not user_id:
            raise AuthError("Authentication required")
        return Principal(user_id=user_id)

    if mode == "aad":
        if not token:
            raise AuthError("Authentication required")
        return Principal(user_id=_user_id_from_aad_jwt(token, settings))

    raise AuthError(f"Unsupported AUTH_MODE {settings.auth_mode!r}")


def _user_id_from_aad_jwt(token: str, settings) -> str:
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
    return str(user_id)

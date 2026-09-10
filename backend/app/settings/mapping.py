"""Map Settings store documents to the Backend PRD HTTP JSON shape."""

from __future__ import annotations

from app.config import microsoft_oauth_configured
from app.settings.constants import DEFAULT_MATCH_THRESHOLD
from app.settings.errors import SettingsValidationError
from app.settings.models import EmailConnection, UserSettings
from app.settings.validation import utc_now

MIN_API_THRESHOLD = 0.10
MAX_API_THRESHOLD = 0.99


def api_threshold(stored: int | None) -> float:
    value = DEFAULT_MATCH_THRESHOLD if stored is None else stored
    return round(value / 100.0, 2)


def db_threshold(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SettingsValidationError("matchThreshold must be a number", path="matchThreshold")
    rounded = round(float(value), 2)
    if rounded < MIN_API_THRESHOLD or rounded > MAX_API_THRESHOLD:
        raise SettingsValidationError(
            f"matchThreshold must be between {MIN_API_THRESHOLD} and {MAX_API_THRESHOLD}",
            path="matchThreshold",
        )
    return int(round(rounded * 100))


def api_email(connection: EmailConnection | None) -> dict:
    if connection is None or connection.status == "revoked":
        return {
            "status": "disconnected",
            "provider": None,
            "tenantId": None,
            "accountId": None,
            "scopes": [],
            "lastVerifiedAt": None,
        }
    status = {
        "pending": "pending",
        "active": "connected",
        "error": "error",
        "expired": "error",
    }.get(connection.status, "error")
    provider = "microsoft" if connection.provider == "microsoft_365" else connection.provider
    body = {
        "status": status,
        "provider": provider,
        "tenantId": connection.tenant_id,
        "accountId": connection.account_id or connection.account_email,
        "scopes": list(connection.scopes),
        "lastVerifiedAt": connection.last_verified_at,
    }
    if status == "error":
        body["errorCode"] = connection.error_code or (
            "expired" if connection.status == "expired" else "error"
        )
    return body


def settings_response(
    settings: UserSettings,
    connection: EmailConnection | None,
    *,
    updated_by: str | None,
) -> dict:
    return {
        "matchThreshold": api_threshold(settings.match_threshold),
        "emailConnection": api_email(connection),
        "oauthConfigured": microsoft_oauth_configured(),
        "sources": {
            "greenhouseEnabled": settings.greenhouse_enabled,
            "leverEnabled": settings.lever_enabled,
        },
        "audit": {
            "createdAt": settings.created_at,
            "updatedAt": settings.updated_at,
            "updatedBy": updated_by or settings.user_id,
        },
    }


def requested_at() -> str:
    return utc_now()

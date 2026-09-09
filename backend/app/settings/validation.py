"""Constraint checks from the Settings Database PRD."""

from __future__ import annotations

from datetime import datetime, timezone

from app.settings.constants import (
    CONNECTION_STATUSES,
    DEFAULT_MATCH_THRESHOLD,
    MAX_MATCH_THRESHOLD,
    MIN_MATCH_THRESHOLD,
    TOKEN_FIELDS,
)
from app.settings.errors import SettingsValidationError
from app.settings.models import EmailConnection, UserSettings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(value: str) -> datetime:
    stamp = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def effective_threshold(settings: UserSettings) -> int:
    if settings.match_threshold is None:
        return DEFAULT_MATCH_THRESHOLD
    return settings.match_threshold


def validate_user_id(user_id: str) -> None:
    if not user_id or not str(user_id).strip():
        raise SettingsValidationError("user_id is required", path="user_id")


def validate_threshold(value: int | None) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool):
        raise SettingsValidationError("match_threshold must be an integer or null", path="match_threshold")
    if value < MIN_MATCH_THRESHOLD or value > MAX_MATCH_THRESHOLD:
        raise SettingsValidationError(
            f"match_threshold must be between {MIN_MATCH_THRESHOLD} and {MAX_MATCH_THRESHOLD}",
            path="match_threshold",
        )


def validate_field_mask(field_mask: list[str]) -> None:
    if not field_mask:
        raise SettingsValidationError("audit field_mask must be non-empty", path="field_mask")


def validate_connection(connection: EmailConnection, *, now: str | None = None) -> None:
    if not connection.provider or not connection.provider.strip():
        raise SettingsValidationError("provider is required", path="provider")
    if connection.status not in CONNECTION_STATUSES:
        raise SettingsValidationError(
            f"status must be one of {sorted(CONNECTION_STATUSES)}",
            path="status",
        )
    has_access = bool(connection.access_token_enc)
    has_refresh = bool(connection.refresh_token_enc)
    if connection.status in {"active", "pending"}:
        if not has_access or not has_refresh:
            raise SettingsValidationError(
                "access_token_enc and refresh_token_enc are required when status is active or pending",
                path="refresh_token_enc",
            )
    if connection.status == "revoked":
        if has_access or has_refresh:
            raise SettingsValidationError(
                "OAuth tokens must be null when status is revoked",
                path="access_token_enc",
            )
    if connection.webhook_subscription_id:
        if not connection.subscription_expires_at:
            raise SettingsValidationError(
                "subscription_expires_at is required when webhook_subscription_id is set",
                path="subscription_expires_at",
            )
        stamp = now or utc_now()
        if parse_ts(connection.subscription_expires_at) < parse_ts(stamp):
            raise SettingsValidationError(
                "subscription_expires_at must be >= now when a webhook subscription exists",
                path="subscription_expires_at",
            )


def redact_detail(detail: dict) -> dict:
    """Drop token material from audit payloads and logs."""
    cleaned: dict = {}
    for key, value in detail.items():
        if key in TOKEN_FIELDS or "token" in key.lower():
            cleaned[key] = None if value is None else "[redacted]"
        elif isinstance(value, dict):
            cleaned[key] = redact_detail(value)
        else:
            cleaned[key] = value
    return cleaned


def connection_is_expired(connection: EmailConnection, *, now: str | None = None) -> bool:
    if connection.status in {"revoked"}:
        return False
    if not connection.expires_at:
        return False
    stamp = now or utc_now()
    return parse_ts(stamp) > parse_ts(connection.expires_at)

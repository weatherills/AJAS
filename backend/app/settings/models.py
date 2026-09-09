"""Pydantic documents for Settings Cosmos containers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.settings.constants import TOKEN_FIELDS, ConnectionStatus, EntityType


def new_id() -> str:
    return str(uuid4())


class UserSettings(BaseModel):
    """One row per user. Cosmos container ``user_settings``, pk ``/user_id``."""

    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    match_threshold: int | None = None
    greenhouse_enabled: bool = False
    lever_enabled: bool = False
    version: int = 1
    created_at: str
    updated_at: str


class EmailConnection(BaseModel):
    """Microsoft 365 OAuth connection. Container ``email_connections``, pk ``/user_id``."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    provider: str = "microsoft_365"
    status: ConnectionStatus
    account_email: str | None = None
    tenant_id: str | None = None
    account_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    access_token_enc: str | None = Field(default=None, repr=False)
    refresh_token_enc: str | None = Field(default=None, repr=False)
    expires_at: str | None = None
    webhook_subscription_id: str | None = None
    subscription_expires_at: str | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    last_verified_at: str | None = None
    error_code: str | None = None
    revoked_at: str | None = None
    created_at: str
    updated_at: str

    @field_serializer("access_token_enc", "refresh_token_enc")
    def _hide_tokens(self, value: str | None) -> str | None:
        return value

    def public_dict(self) -> dict[str, Any]:
        """JSON-safe view with OAuth tokens removed."""
        payload = self.model_dump()
        for field in TOKEN_FIELDS:
            payload.pop(field, None)
        return payload


class SettingsAuditEntry(BaseModel):
    """Append-only change log. Container ``settings_audit_log``, pk ``/user_id``."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    entity_type: EntityType
    entity_id: str
    actor_id: str
    field_mask: list[str]
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str

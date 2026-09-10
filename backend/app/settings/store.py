"""Settings store protocol and factory."""

from __future__ import annotations

from typing import Protocol

from app.settings.models import EmailConnection, SettingsAuditEntry, UserSettings


class SettingsStore(Protocol):
    def get_or_create_settings(self, user_id: str, *, actor_id: str | None = None) -> UserSettings: ...

    def get_settings(self, user_id: str) -> UserSettings: ...

    def update_settings(
        self,
        user_id: str,
        *,
        actor_id: str,
        expected_version: int,
        match_threshold: object = ...,
        greenhouse_enabled: object = ...,
        lever_enabled: object = ...,
        auto_apply_enabled: object = ...,
    ) -> UserSettings: ...

    def effective_threshold(self, user_id: str) -> int: ...

    def list_connections(self, user_id: str) -> list[EmailConnection]: ...

    def get_connection(self, user_id: str, connection_id: str) -> EmailConnection: ...

    def get_active_connection(self, user_id: str, provider: str = "microsoft_365") -> EmailConnection | None: ...

    def upsert_connection(
        self,
        user_id: str,
        connection: EmailConnection,
        *,
        actor_id: str,
    ) -> EmailConnection: ...

    def revoke_connection(self, user_id: str, connection_id: str, *, actor_id: str) -> EmailConnection: ...

    def record_sync(
        self,
        user_id: str,
        connection_id: str,
        *,
        actor_id: str,
        last_sync_status: str,
        last_sync_error: str | None = None,
    ) -> EmailConnection: ...

    def list_audit(self, user_id: str, *, entity_id: str | None = None) -> list[SettingsAuditEntry]: ...

    def delete_user_data(self, user_id: str, *, actor_id: str) -> None: ...


def get_settings_store() -> SettingsStore:
    from app.config import get_settings
    from app.settings.memory import InMemorySettingsStore

    settings = get_settings()
    if not settings.cosmos_connection_string:
        return InMemorySettingsStore()
    from app.settings.cosmos_store import CosmosSettingsStore
    from app.storage.cosmos import get_database

    return CosmosSettingsStore(get_database())

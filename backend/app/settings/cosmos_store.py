"""Cosmos DB implementation of SettingsStore."""

from __future__ import annotations

from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.settings.constants import AUDIT_CONTAINER, CONNECTIONS_CONTAINER, SETTINGS_CONTAINER
from app.settings.errors import SettingsNotFoundError
from app.settings.memory import InMemorySettingsStore
from app.settings.models import EmailConnection, SettingsAuditEntry, UserSettings


class CosmosSettingsStore:
    """Persists settings using the same rules as ``InMemorySettingsStore``."""

    def __init__(self, database: Any) -> None:
        self._settings = database.get_container_client(SETTINGS_CONTAINER)
        self._connections = database.get_container_client(CONNECTIONS_CONTAINER)
        self._audit = database.get_container_client(AUDIT_CONTAINER)

    def get_or_create_settings(self, user_id: str, *, actor_id: str | None = None) -> UserSettings:
        working = self._hydrate(user_id)
        created = working.get_or_create_settings(user_id, actor_id=actor_id)
        self._persist_settings(created)
        self._persist_new_audit(working, user_id)
        return created

    def get_settings(self, user_id: str) -> UserSettings:
        try:
            item = self._settings.read_item(item=user_id, partition_key=user_id)
        except CosmosResourceNotFoundError as exc:
            raise SettingsNotFoundError(user_id) from exc
        return UserSettings.model_validate(item)

    def list_user_ids(self) -> list[str]:
        ids: set[str] = set()
        for client in (self._settings, self._connections):
            try:
                rows = client.query_items(query="SELECT c.user_id FROM c", enable_cross_partition_query=True)
            except TypeError:
                rows = client.query_items(query="SELECT c.user_id FROM c")
            for item in rows:
                user_id = item.get("user_id")
                if user_id:
                    ids.add(str(user_id))
        return sorted(ids)

    def update_settings(self, user_id: str, **kwargs: Any) -> UserSettings:
        working = self._hydrate(user_id)
        updated = working.update_settings(user_id, **kwargs)
        self._persist_settings(updated)
        self._persist_new_audit(working, user_id)
        return updated

    def effective_threshold(self, user_id: str) -> int:
        working = self._hydrate(user_id)
        value = working.effective_threshold(user_id)
        settings = working.get_settings(user_id)
        self._persist_settings(settings)
        self._persist_new_audit(working, user_id)
        return value

    def list_connections(self, user_id: str) -> list[EmailConnection]:
        working = self._hydrate(user_id)
        rows = working.list_connections(user_id)
        for row in rows:
            self._persist_connection(row)
        self._persist_new_audit(working, user_id)
        return rows

    def get_connection(self, user_id: str, connection_id: str) -> EmailConnection:
        working = self._hydrate(user_id)
        row = working.get_connection(user_id, connection_id)
        self._persist_connection(row)
        self._persist_new_audit(working, user_id)
        return row

    def get_active_connection(self, user_id: str, provider: str = "microsoft_365") -> EmailConnection | None:
        working = self._hydrate(user_id)
        row = working.get_active_connection(user_id, provider)
        for item in working.list_connections(user_id):
            self._persist_connection(item)
        self._persist_new_audit(working, user_id)
        return row

    def upsert_connection(self, user_id: str, connection: EmailConnection, *, actor_id: str) -> EmailConnection:
        working = self._hydrate(user_id)
        saved = working.upsert_connection(user_id, connection, actor_id=actor_id)
        self._persist_connection(saved)
        self._persist_new_audit(working, user_id)
        return saved

    def revoke_connection(self, user_id: str, connection_id: str, *, actor_id: str) -> EmailConnection:
        working = self._hydrate(user_id)
        saved = working.revoke_connection(user_id, connection_id, actor_id=actor_id)
        self._persist_connection(saved)
        self._persist_new_audit(working, user_id)
        return saved

    def record_sync(self, user_id: str, connection_id: str, **kwargs: Any) -> EmailConnection:
        working = self._hydrate(user_id)
        saved = working.record_sync(user_id, connection_id, **kwargs)
        self._persist_connection(saved)
        self._persist_new_audit(working, user_id)
        return saved

    def list_audit(self, user_id: str, *, entity_id: str | None = None) -> list[SettingsAuditEntry]:
        query = "SELECT * FROM c WHERE c.user_id = @user_id"
        params: list[dict[str, str]] = [{"name": "@user_id", "value": user_id}]
        if entity_id:
            query += " AND c.entity_id = @entity_id"
            params.append({"name": "@entity_id", "value": entity_id})
        query += " ORDER BY c.created_at DESC"
        items = self._audit.query_items(query=query, parameters=params, partition_key=user_id)
        return [SettingsAuditEntry.model_validate(item) for item in items]

    def delete_user_data(self, user_id: str, *, actor_id: str) -> None:
        working = self._hydrate(user_id)
        snapshot_connections = list(working.list_connections(user_id))
        working.delete_user_data(user_id, actor_id=actor_id)
        try:
            self._settings.delete_item(item=user_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            pass
        for connection in snapshot_connections:
            try:
                self._connections.delete_item(item=connection.id, partition_key=user_id)
            except CosmosResourceNotFoundError:
                pass
        self._persist_new_audit(working, user_id)

    def _hydrate(self, user_id: str) -> InMemorySettingsStore:
        working = InMemorySettingsStore()
        try:
            item = self._settings.read_item(item=user_id, partition_key=user_id)
            settings = UserSettings.model_validate(item)
            working._settings[user_id] = settings  # noqa: SLF001
        except CosmosResourceNotFoundError:
            pass
        items = self._connections.query_items(
            query="SELECT * FROM c WHERE c.user_id = @user_id",
            parameters=[{"name": "@user_id", "value": user_id}],
            partition_key=user_id,
        )
        bucket: dict[str, EmailConnection] = {}
        for item in items:
            connection = EmailConnection.model_validate(item)
            bucket[connection.id] = connection
        working._connections[user_id] = bucket  # noqa: SLF001
        working._audit[user_id] = self.list_audit(user_id)  # noqa: SLF001
        return working

    def _persist_settings(self, settings: UserSettings) -> None:
        payload = settings.model_dump()
        try:
            self._settings.replace_item(item=settings.id, body=payload)
        except CosmosResourceNotFoundError:
            self._settings.create_item(body=payload)

    def _persist_connection(self, connection: EmailConnection) -> None:
        payload = connection.model_dump()
        try:
            self._connections.replace_item(item=connection.id, body=payload)
        except CosmosResourceNotFoundError:
            self._connections.create_item(body=payload)

    def _persist_new_audit(self, working: InMemorySettingsStore, user_id: str) -> None:
        existing_ids = {entry.id for entry in self.list_audit(user_id)}
        for entry in working.list_audit(user_id):
            if entry.id not in existing_ids:
                self._audit.create_item(body=entry.model_dump())

"""In-memory SettingsStore used by tests and local work without Cosmos."""

from __future__ import annotations

from copy import deepcopy

from app.settings.constants import DEFAULT_MATCH_THRESHOLD
from app.settings.errors import (
    SettingsConflictError,
    SettingsNotFoundError,
    SettingsValidationError,
)
from app.settings.models import EmailConnection, SettingsAuditEntry, UserSettings, new_id
from app.settings.validation import (
    connection_is_expired,
    redact_detail,
    utc_now,
    validate_connection,
    validate_field_mask,
    validate_threshold,
    validate_user_id,
)

UNSET = object()


class InMemorySettingsStore:
    """Reference implementation of the Settings Database PRD behaviors."""

    def __init__(self) -> None:
        self._settings: dict[str, UserSettings] = {}
        self._connections: dict[str, dict[str, EmailConnection]] = {}
        self._audit: dict[str, list[SettingsAuditEntry]] = {}
        self.refresh_queue: list[dict[str, str]] = []

    def get_or_create_settings(self, user_id: str, *, actor_id: str | None = None) -> UserSettings:
        validate_user_id(user_id)
        existing = self._settings.get(user_id)
        if existing is not None:
            return deepcopy(existing)
        now = utc_now()
        settings = UserSettings(
            id=user_id,
            user_id=user_id,
            match_threshold=None,
            greenhouse_enabled=False,
            lever_enabled=False,
            greenhouse_explicit=False,
            lever_explicit=False,
            auto_apply_enabled=True,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._settings[user_id] = settings
        self._audit_write(
            user_id=user_id,
            entity_type="user_settings",
            entity_id=settings.id,
            actor_id=actor_id or user_id,
            field_mask=["created"],
            detail={
                "match_threshold": None,
                "greenhouse_enabled": False,
                "lever_enabled": False,
                "greenhouse_explicit": False,
                "lever_explicit": False,
                "auto_apply_enabled": True,
            },
        )
        return deepcopy(settings)

    def get_settings(self, user_id: str) -> UserSettings:
        validate_user_id(user_id)
        settings = self._settings.get(user_id)
        if settings is None:
            raise SettingsNotFoundError(user_id)
        return deepcopy(settings)

    def update_settings(
        self,
        user_id: str,
        *,
        actor_id: str,
        expected_version: int,
        match_threshold: object = UNSET,
        greenhouse_enabled: object = UNSET,
        lever_enabled: object = UNSET,
        auto_apply_enabled: object = UNSET,
    ) -> UserSettings:
        settings = self._require_settings(user_id)
        if settings.version != expected_version:
            raise SettingsConflictError(
                f"version mismatch: stored {settings.version}, expected {expected_version}"
            )
        changes: dict = {}
        if match_threshold is not UNSET:
            if match_threshold is not None and type(match_threshold) is not int:
                raise SettingsValidationError(
                    "match_threshold must be an integer or null", path="match_threshold"
                )
            validate_threshold(match_threshold)  # type: ignore[arg-type]
            if settings.match_threshold != match_threshold:
                changes["match_threshold"] = {
                    "from": settings.match_threshold,
                    "to": match_threshold,
                }
                settings.match_threshold = match_threshold  # type: ignore[assignment]
        if greenhouse_enabled is not UNSET:
            if not isinstance(greenhouse_enabled, bool):
                raise SettingsValidationError("greenhouse_enabled must be a boolean", path="greenhouse_enabled")
            if settings.greenhouse_enabled != greenhouse_enabled or not settings.greenhouse_explicit:
                changes["greenhouse_enabled"] = {
                    "from": settings.greenhouse_enabled,
                    "to": greenhouse_enabled,
                }
                settings.greenhouse_enabled = greenhouse_enabled
                settings.greenhouse_explicit = True
        if lever_enabled is not UNSET:
            if not isinstance(lever_enabled, bool):
                raise SettingsValidationError("lever_enabled must be a boolean", path="lever_enabled")
            if settings.lever_enabled != lever_enabled or not settings.lever_explicit:
                changes["lever_enabled"] = {"from": settings.lever_enabled, "to": lever_enabled}
                settings.lever_enabled = lever_enabled
                settings.lever_explicit = True
        if auto_apply_enabled is not UNSET:
            if not isinstance(auto_apply_enabled, bool):
                raise SettingsValidationError("auto_apply_enabled must be a boolean", path="auto_apply_enabled")
            if settings.auto_apply_enabled != auto_apply_enabled:
                changes["auto_apply_enabled"] = {
                    "from": settings.auto_apply_enabled,
                    "to": auto_apply_enabled,
                }
                settings.auto_apply_enabled = auto_apply_enabled
        if not changes:
            return deepcopy(settings)
        settings.version += 1
        settings.updated_at = utc_now()
        self._settings[user_id] = settings
        self._audit_write(
            user_id=user_id,
            entity_type="user_settings",
            entity_id=settings.id,
            actor_id=actor_id,
            field_mask=sorted(changes),
            detail=changes,
        )
        return deepcopy(settings)

    def effective_threshold(self, user_id: str) -> int:
        settings = self.get_or_create_settings(user_id)
        if settings.match_threshold is None:
            return DEFAULT_MATCH_THRESHOLD
        return settings.match_threshold

    def list_connections(self, user_id: str) -> list[EmailConnection]:
        validate_user_id(user_id)
        self._expire_due(user_id)
        rows = list(self._connections.get(user_id, {}).values())
        rows.sort(key=lambda item: item.updated_at, reverse=True)
        return [deepcopy(item) for item in rows]

    def get_connection(self, user_id: str, connection_id: str) -> EmailConnection:
        validate_user_id(user_id)
        self._expire_due(user_id, connection_id=connection_id)
        connection = self._connections.get(user_id, {}).get(connection_id)
        if connection is None:
            raise SettingsNotFoundError(connection_id)
        return deepcopy(connection)

    def get_active_connection(self, user_id: str, provider: str = "microsoft_365") -> EmailConnection | None:
        for item in self.list_connections(user_id):
            if item.provider == provider and item.status == "active":
                return item
        return None

    def upsert_connection(
        self,
        user_id: str,
        connection: EmailConnection,
        *,
        actor_id: str,
    ) -> EmailConnection:
        validate_user_id(user_id)
        if connection.user_id != user_id:
            raise SettingsValidationError("connection.user_id must match caller", path="user_id")
        now = utc_now()
        validate_connection(connection, now=now)
        bucket = self._connections.setdefault(user_id, {})
        previous = bucket.get(connection.id)
        if connection.status == "active":
            for other in bucket.values():
                if (
                    other.id != connection.id
                    and other.provider == connection.provider
                    and other.status == "active"
                ):
                    raise SettingsConflictError(
                        "only one active email connection is allowed per user and provider"
                    )
        field_mask = _diff_connection(previous, connection)
        if not field_mask:
            field_mask = ["created"] if previous is None else ["updated"]
        connection.updated_at = now
        if previous is None:
            connection.created_at = connection.created_at or now
        bucket[connection.id] = connection
        self._audit_write(
            user_id=user_id,
            entity_type="email_connections",
            entity_id=connection.id,
            actor_id=actor_id,
            field_mask=field_mask,
            detail=_connection_audit_detail(previous, connection),
        )
        return deepcopy(connection)

    def revoke_connection(self, user_id: str, connection_id: str, *, actor_id: str) -> EmailConnection:
        connection = self._require_connection(user_id, connection_id)
        now = utc_now()
        connection.access_token_enc = None
        connection.refresh_token_enc = None
        connection.status = "revoked"
        connection.revoked_at = now
        connection.updated_at = now
        self._connections[user_id][connection_id] = connection
        self._audit_write(
            user_id=user_id,
            entity_type="email_connections",
            entity_id=connection.id,
            actor_id=actor_id,
            field_mask=["status", "access_token_enc", "refresh_token_enc", "revoked_at"],
            detail={"status": {"to": "revoked"}, "tokens_cleared": True, "revoked_at": now},
        )
        return deepcopy(connection)

    def record_sync(
        self,
        user_id: str,
        connection_id: str,
        *,
        actor_id: str,
        last_sync_status: str,
        last_sync_error: str | None = None,
    ) -> EmailConnection:
        connection = self._require_connection(user_id, connection_id)
        connection.last_sync_status = last_sync_status
        connection.last_sync_error = last_sync_error
        connection.updated_at = utc_now()
        self._connections[user_id][connection_id] = connection
        self._audit_write(
            user_id=user_id,
            entity_type="email_connections",
            entity_id=connection.id,
            actor_id=actor_id,
            field_mask=["last_sync_status", "last_sync_error"],
            detail={"last_sync_status": last_sync_status, "last_sync_error": last_sync_error},
        )
        return deepcopy(connection)

    def list_audit(self, user_id: str, *, entity_id: str | None = None) -> list[SettingsAuditEntry]:
        validate_user_id(user_id)
        rows = list(self._audit.get(user_id, []))
        if entity_id:
            rows = [item for item in rows if item.entity_id == entity_id]
        rows.sort(key=lambda item: item.created_at, reverse=True)
        return [deepcopy(item) for item in rows]

    def delete_user_data(self, user_id: str, *, actor_id: str) -> None:
        """Remove settings and connections; audit log stays immutable."""
        validate_user_id(user_id)
        settings = self._settings.pop(user_id, None)
        connections = self._connections.pop(user_id, {})
        field_mask = ["deleted"]
        if settings is not None:
            self._audit_write(
                user_id=user_id,
                entity_type="user_settings",
                entity_id=settings.id,
                actor_id=actor_id,
                field_mask=field_mask,
                detail={"deleted": True},
            )
        for connection in connections.values():
            self._audit_write(
                user_id=user_id,
                entity_type="email_connections",
                entity_id=connection.id,
                actor_id=actor_id,
                field_mask=field_mask,
                detail={"deleted": True},
            )

    def _expire_due(self, user_id: str, *, connection_id: str | None = None) -> None:
        bucket = self._connections.get(user_id, {})
        targets = [bucket[connection_id]] if connection_id and connection_id in bucket else list(bucket.values())
        now = utc_now()
        for connection in targets:
            if connection.status in {"revoked", "expired"}:
                continue
            if connection_is_expired(connection, now=now):
                connection.status = "expired"
                connection.updated_at = now
                bucket[connection.id] = connection
                self.refresh_queue.append({"user_id": user_id, "connection_id": connection.id})
                self._audit_write(
                    user_id=user_id,
                    entity_type="email_connections",
                    entity_id=connection.id,
                    actor_id=user_id,
                    field_mask=["status"],
                    detail={"status": {"to": "expired"}, "tokens_retained": True},
                )

    def _require_settings(self, user_id: str) -> UserSettings:
        validate_user_id(user_id)
        settings = self._settings.get(user_id)
        if settings is None:
            raise SettingsNotFoundError(user_id)
        return settings

    def _require_connection(self, user_id: str, connection_id: str) -> EmailConnection:
        validate_user_id(user_id)
        connection = self._connections.get(user_id, {}).get(connection_id)
        if connection is None:
            raise SettingsNotFoundError(connection_id)
        return connection

    def _audit_write(
        self,
        *,
        user_id: str,
        entity_type: str,
        entity_id: str,
        actor_id: str,
        field_mask: list[str],
        detail: dict,
    ) -> None:
        validate_field_mask(field_mask)
        entry = SettingsAuditEntry(
            id=new_id(),
            user_id=user_id,
            entity_type=entity_type,  # type: ignore[arg-type]
            entity_id=entity_id,
            actor_id=actor_id,
            field_mask=list(field_mask),
            detail=redact_detail(detail),
            created_at=utc_now(),
        )
        self._audit.setdefault(user_id, []).append(entry)


def _diff_connection(previous: EmailConnection | None, current: EmailConnection) -> list[str]:
    if previous is None:
        return ["created"]
    mask: list[str] = []
    skip = {"updated_at", "created_at"}
    prev = previous.model_dump()
    nxt = current.model_dump()
    for key, value in nxt.items():
        if key in skip:
            continue
        if prev.get(key) != value:
            mask.append(key)
    return mask


def _connection_audit_detail(previous: EmailConnection | None, current: EmailConnection) -> dict:
    body = {"status": current.status, "provider": current.provider}
    if previous and previous.status != current.status:
        body["status"] = {"from": previous.status, "to": current.status}
    if current.access_token_enc or current.refresh_token_enc:
        body["tokens_present"] = True
    return body

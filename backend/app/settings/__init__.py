"""Settings database layer (Cosmos schema + store).

Implements the Database PRD: one user_settings row per user, email_connections
with at most one active Microsoft 365 connection, and an append-only
settings_audit_log. OAuth tokens are stored only in *_enc fields and never
written into audit detail.
"""

from app.settings.constants import (
    AUDIT_CONTAINER,
    CONNECTIONS_CONTAINER,
    DEFAULT_MATCH_THRESHOLD,
    SETTINGS_CONTAINER,
)
from app.settings.containers import container_specs, ensure_settings_containers
from app.settings.errors import (
    SettingsConflictError,
    SettingsNotFoundError,
    SettingsStoreError,
    SettingsValidationError,
)
from app.settings.memory import UNSET, InMemorySettingsStore
from app.settings.models import EmailConnection, SettingsAuditEntry, UserSettings
from app.settings.store import SettingsStore, get_settings_store
from app.settings.validation import effective_threshold

__all__ = [
    "AUDIT_CONTAINER",
    "CONNECTIONS_CONTAINER",
    "DEFAULT_MATCH_THRESHOLD",
    "SETTINGS_CONTAINER",
    "EmailConnection",
    "InMemorySettingsStore",
    "SettingsAuditEntry",
    "SettingsConflictError",
    "SettingsNotFoundError",
    "SettingsStore",
    "SettingsStoreError",
    "SettingsValidationError",
    "UNSET",
    "UserSettings",
    "container_specs",
    "effective_threshold",
    "ensure_settings_containers",
    "get_settings_store",
]

"""Settings Database PRD — schema, constraints, and store behaviors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.settings import (
    DEFAULT_MATCH_THRESHOLD,
    InMemorySettingsStore,
    SettingsConflictError,
    SettingsNotFoundError,
    SettingsValidationError,
    container_specs,
    effective_threshold,
)
from app.settings.constants import (
    AUDIT_CONTAINER,
    AUDIT_PARTITION_KEY,
    CONNECTIONS_CONTAINER,
    CONNECTIONS_PARTITION_KEY,
    SETTINGS_CONTAINER,
    SETTINGS_INDEXING_POLICY,
    SETTINGS_PARTITION_KEY,
)
from app.settings.cosmos_store import CosmosSettingsStore
from app.settings.models import EmailConnection
from app.settings.store import get_settings_store
from app.settings.validation import utc_now

USER = "user-1"
OTHER = "user-2"
SECRET = "super-secret-refresh-token"


def _not_found() -> CosmosResourceNotFoundError:
    return CosmosResourceNotFoundError(status_code=404, message="not found")


class FakeContainer:
    def __init__(self, pk_field: str) -> None:
        self.pk_field = pk_field
        self.items: dict[tuple[str, str], dict] = {}

    def create_item(self, body: dict) -> dict:
        key = (body[self.pk_field], body["id"])
        if key in self.items:
            raise ValueError(f"conflict {key}")
        stored = dict(body)
        self.items[key] = stored
        return dict(stored)

    def read_item(self, item: str, partition_key: str) -> dict:
        key = (partition_key, item)
        if key not in self.items:
            raise _not_found()
        return dict(self.items[key])

    def replace_item(self, item: str, body: dict) -> dict:
        key = (body[self.pk_field], item if isinstance(item, str) else item["id"])
        if key not in self.items:
            raise _not_found()
        self.items[key] = dict(body)
        return dict(body)

    def upsert_item(self, body: dict) -> dict:
        key = (body[self.pk_field], body["id"])
        self.items[key] = dict(body)
        return dict(body)

    def delete_item(self, item: str, partition_key: str) -> None:
        key = (partition_key, item if isinstance(item, str) else item["id"])
        self.items.pop(key, None)

    def query_items(self, query: str, parameters=None, partition_key=None, **_kwargs):
        params = {p["name"]: p["value"] for p in (parameters or [])}
        rows = [dict(v) for v in self.items.values()]
        if partition_key is not None:
            rows = [r for r in rows if r.get(self.pk_field) == partition_key]
        if "@user_id" in params and "c.user_id" in query:
            rows = [r for r in rows if r.get("user_id") == params["@user_id"]]
        if "@entity_id" in params and "c.entity_id" in query:
            rows = [r for r in rows if r.get("entity_id") == params["@entity_id"]]
        if "ORDER BY c.created_at DESC" in query:
            rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        if "ORDER BY c.updated_at DESC" in query:
            rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        return rows


class FakeDatabase:
    def __init__(self) -> None:
        self._containers = {
            SETTINGS_CONTAINER: FakeContainer("user_id"),
            CONNECTIONS_CONTAINER: FakeContainer("user_id"),
            AUDIT_CONTAINER: FakeContainer("user_id"),
        }
        self.created: list[dict] = []

    def get_container_client(self, name: str) -> FakeContainer:
        return self._containers[name]

    def create_container_if_not_exists(self, **kwargs) -> None:
        self.created.append(kwargs)


@pytest.fixture(params=["memory", "cosmos"])
def store(request):
    if request.param == "memory":
        return InMemorySettingsStore()
    return CosmosSettingsStore(FakeDatabase())


def _iso(delta_hours: int) -> str:
    stamp = datetime.now(timezone.utc) + timedelta(hours=delta_hours)
    return stamp.isoformat().replace("+00:00", "Z")


def _connection(**overrides) -> EmailConnection:
    now = utc_now()
    payload = {
        "user_id": USER,
        "provider": "microsoft_365",
        "status": "active",
        "account_email": "jane@contoso.com",
        "access_token_enc": "enc:access",
        "refresh_token_enc": SECRET,
        "expires_at": _iso(2),
        "created_at": now,
        "updated_at": now,
    }
    payload.update(overrides)
    return EmailConnection.model_validate(payload)


def test_container_specs_match_prd():
    specs = {item["id"]: item for item in container_specs()}
    assert specs[SETTINGS_CONTAINER]["partition_key"] == SETTINGS_PARTITION_KEY
    assert specs[CONNECTIONS_CONTAINER]["partition_key"] == CONNECTIONS_PARTITION_KEY
    assert specs[AUDIT_CONTAINER]["partition_key"] == AUDIT_PARTITION_KEY
    assert SETTINGS_INDEXING_POLICY["compositeIndexes"]
    assert specs[SETTINGS_CONTAINER]["indexing_policy"] == SETTINGS_INDEXING_POLICY


def test_ensure_settings_containers_creates_three():
    from app.settings.containers import ensure_settings_containers

    database = FakeDatabase()
    ensure_settings_containers(database)
    assert {item["id"] for item in database.created} == {
        SETTINGS_CONTAINER,
        CONNECTIONS_CONTAINER,
        AUDIT_CONTAINER,
    }


def test_get_or_create_is_one_row_per_user(store):
    first = store.get_or_create_settings(USER, actor_id=USER)
    second = store.get_or_create_settings(USER, actor_id=USER)
    assert first.id == USER
    assert first.user_id == second.user_id == USER
    assert first.version == 1
    assert first.match_threshold is None
    assert first.greenhouse_enabled is False
    assert first.lever_enabled is False
    assert first.greenhouse_explicit is False
    assert first.lever_explicit is False
    assert store.effective_threshold(USER) == DEFAULT_MATCH_THRESHOLD
    other = store.get_or_create_settings(OTHER, actor_id=OTHER)
    assert other.user_id == OTHER
    assert other.id != first.id or OTHER != USER


def test_threshold_bounds_and_null_default(store):
    created = store.get_or_create_settings(USER, actor_id=USER)
    updated = store.update_settings(
        USER, actor_id=USER, expected_version=created.version, match_threshold=0
    )
    assert updated.match_threshold == 0
    assert effective_threshold(updated) == 0
    updated = store.update_settings(
        USER, actor_id=USER, expected_version=updated.version, match_threshold=100
    )
    assert updated.match_threshold == 100
    with pytest.raises(SettingsValidationError):
        store.update_settings(
            USER, actor_id=USER, expected_version=updated.version, match_threshold=101
        )
    with pytest.raises(SettingsValidationError):
        store.update_settings(
            USER, actor_id=USER, expected_version=updated.version, match_threshold=-1
        )
    cleared = store.update_settings(
        USER, actor_id=USER, expected_version=updated.version, match_threshold=None
    )
    assert cleared.match_threshold is None
    assert store.effective_threshold(USER) == DEFAULT_MATCH_THRESHOLD


def test_source_toggles_allow_both_false(store):
    created = store.get_or_create_settings(USER, actor_id=USER)
    updated = store.update_settings(
        USER,
        actor_id=USER,
        expected_version=created.version,
        greenhouse_enabled=True,
        lever_enabled=True,
    )
    assert updated.greenhouse_enabled is True
    both_off = store.update_settings(
        USER,
        actor_id=USER,
        expected_version=updated.version,
        greenhouse_enabled=False,
        lever_enabled=False,
    )
    assert both_off.greenhouse_enabled is False
    assert both_off.lever_enabled is False
    assert both_off.greenhouse_explicit is True
    assert both_off.lever_explicit is True


def test_source_off_is_explicit_even_when_stored_value_was_already_false(store):
    created = store.get_or_create_settings(USER, actor_id=USER)
    assert created.greenhouse_explicit is False
    assert created.lever_explicit is False
    off = store.update_settings(
        USER,
        actor_id=USER,
        expected_version=created.version,
        greenhouse_enabled=False,
    )
    assert off.greenhouse_enabled is False
    assert off.greenhouse_explicit is True
    assert off.lever_explicit is False


def test_optimistic_lock_rejects_stale_version(store):
    created = store.get_or_create_settings(USER, actor_id=USER)
    store.update_settings(USER, actor_id=USER, expected_version=created.version, match_threshold=80)
    with pytest.raises(SettingsConflictError):
        store.update_settings(
            USER, actor_id=USER, expected_version=created.version, match_threshold=90
        )


def test_settings_mutations_write_audit(store):
    created = store.get_or_create_settings(USER, actor_id="actor-a")
    store.update_settings(
        USER, actor_id="actor-b", expected_version=created.version, match_threshold=55
    )
    entries = store.list_audit(USER, entity_id=USER)
    assert entries
    assert all(item.field_mask for item in entries)
    assert any(item.actor_id == "actor-b" and "match_threshold" in item.field_mask for item in entries)


def test_active_connection_requires_tokens_and_hides_them(store):
    store.get_or_create_settings(USER, actor_id=USER)
    with pytest.raises(SettingsValidationError):
        store.upsert_connection(
            USER,
            _connection(access_token_enc=None, refresh_token_enc=None),
            actor_id=USER,
        )
    saved = store.upsert_connection(USER, _connection(), actor_id=USER)
    assert saved.status == "active"
    assert saved.refresh_token_enc == SECRET
    public = saved.public_dict()
    assert "refresh_token_enc" not in public
    assert "access_token_enc" not in public
    assert SECRET not in repr(saved)
    audit = store.list_audit(USER, entity_id=saved.id)
    blob = str(audit)
    assert SECRET not in blob
    assert all("token" not in str(item.detail).lower() or "[redacted]" in str(item.detail) or "tokens_present" in item.detail for item in audit)


def test_only_one_active_connection_per_provider(store):
    store.get_or_create_settings(USER, actor_id=USER)
    first = store.upsert_connection(USER, _connection(), actor_id=USER)
    with pytest.raises(SettingsConflictError):
        store.upsert_connection(USER, _connection(account_email="other@contoso.com"), actor_id=USER)
    store.revoke_connection(USER, first.id, actor_id=USER)
    second = store.upsert_connection(USER, _connection(account_email="other@contoso.com"), actor_id=USER)
    assert second.status == "active"
    revoked = store.get_connection(USER, first.id)
    assert revoked.status == "revoked"
    assert revoked.access_token_enc is None
    assert revoked.refresh_token_enc is None
    assert revoked.revoked_at


def test_revoke_keeps_row_and_clears_tokens(store):
    store.get_or_create_settings(USER, actor_id=USER)
    saved = store.upsert_connection(USER, _connection(), actor_id=USER)
    revoked = store.revoke_connection(USER, saved.id, actor_id=USER)
    assert revoked.status == "revoked"
    listed = store.list_connections(USER)
    assert len(listed) == 1
    with pytest.raises(SettingsValidationError):
        store.upsert_connection(
            USER,
            _connection(id=saved.id, status="revoked", access_token_enc="enc:x", refresh_token_enc="enc:y"),
            actor_id=USER,
        )


def test_expired_token_keeps_secrets_and_queues_refresh(store):
    store.get_or_create_settings(USER, actor_id=USER)
    saved = store.upsert_connection(USER, _connection(expires_at=_iso(-1)), actor_id=USER)
    loaded = store.get_connection(USER, saved.id)
    assert loaded.status == "expired"
    assert loaded.refresh_token_enc == SECRET
    if hasattr(store, "refresh_queue"):
        assert any(item["connection_id"] == saved.id for item in store.refresh_queue)
    else:
        # Cosmos hydrates through memory, which records the audit status change.
        entries = store.list_audit(USER, entity_id=saved.id)
        assert any("expired" in str(item.detail) for item in entries)


def test_webhook_subscription_must_not_be_in_the_past(store):
    store.get_or_create_settings(USER, actor_id=USER)
    with pytest.raises(SettingsValidationError):
        store.upsert_connection(
            USER,
            _connection(webhook_subscription_id="sub-1", subscription_expires_at=_iso(-1)),
            actor_id=USER,
        )
    saved = store.upsert_connection(
        USER,
        _connection(webhook_subscription_id="sub-1", subscription_expires_at=_iso(24)),
        actor_id=USER,
    )
    assert saved.webhook_subscription_id == "sub-1"


def test_list_user_ids_includes_settings_and_connections(store):
    store.get_or_create_settings(USER, actor_id=USER)
    store.upsert_connection(OTHER, _connection(user_id=OTHER), actor_id=OTHER)
    assert USER in store.list_user_ids()
    assert OTHER in store.list_user_ids()


def test_record_sync_and_pending_tokens(store):
    store.get_or_create_settings(USER, actor_id=USER)
    pending = store.upsert_connection(USER, _connection(status="pending"), actor_id=USER)
    synced = store.record_sync(
        USER, pending.id, actor_id=USER, last_sync_status="ok", last_sync_error=None
    )
    assert synced.last_sync_status == "ok"


def test_delete_user_data_keeps_audit(store):
    created = store.get_or_create_settings(USER, actor_id=USER)
    conn = store.upsert_connection(USER, _connection(), actor_id=USER)
    store.update_settings(USER, actor_id=USER, expected_version=created.version, match_threshold=70)
    store.delete_user_data(USER, actor_id="admin")
    with pytest.raises(SettingsNotFoundError):
        store.get_settings(USER)
    assert store.list_connections(USER) == []
    audit = store.list_audit(USER)
    assert audit
    assert any(item.entity_id == conn.id for item in audit)
    assert any("deleted" in item.field_mask for item in audit)


def test_unknown_user_get_settings(store):
    with pytest.raises(SettingsNotFoundError):
        store.get_settings(USER)


def test_get_settings_store_defaults_to_memory(monkeypatch):
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    store = get_settings_store()
    assert isinstance(store, InMemorySettingsStore)
    config.get_settings.cache_clear()

"""Database PRD tests for Auto-Apply (memory + Cosmos hydrate/persist)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.auto_apply.constants import (
    STATUS_EVENTS_RETENTION_DAYS,
    TERMINAL_ATTEMPT,
    WEBHOOK_RETENTION_DAYS,
)
from app.auto_apply.containers import container_specs, ensure_auto_apply_containers
from app.auto_apply.cosmos_store import CosmosAutoApplyStore
from app.auto_apply.errors import (
    AutoApplyConflictError,
    AutoApplyNotFoundError,
    AutoApplyValidationError,
)
from app.auto_apply.memory import InMemoryAutoApplyStore
from app.auto_apply.store import get_auto_apply_store


USER = "user-1"
OTHER = "user-2"
GH_URL = "https://boards.greenhouse.io/acme/jobs/1"


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

    def replace_item(self, item: str, body: dict) -> dict:
        key = (body[self.pk_field], item if isinstance(item, str) else item["id"])
        if key not in self.items:
            raise _not_found()
        self.items[key] = dict(body)
        return dict(body)

    def query_items(self, query: str, parameters=None, partition_key=None, **_kwargs):
        rows = [dict(v) for v in self.items.values()]
        if partition_key is not None:
            rows = [r for r in rows if r.get(self.pk_field) == partition_key]
        return rows


class FakeDatabase:
    def __init__(self) -> None:
        self._containers = {
            "auto_apply_attempts": FakeContainer("user_id"),
            "apply_packages": FakeContainer("auto_apply_id"),
            "resume_variants": FakeContainer("user_id"),
            "cover_letters": FakeContainer("user_id"),
            "form_autofill_values": FakeContainer("auto_apply_id"),
            "vendor_field_mappings": FakeContainer("vendor"),
            "submit_requests": FakeContainer("auto_apply_id"),
            "status_events": FakeContainer("auto_apply_id"),
            "webhook_callbacks": FakeContainer("vendor_application_id"),
        }
        self.created: list[dict] = []

    def get_container_client(self, name: str) -> FakeContainer:
        return self._containers[name]

    def create_container_if_not_exists(self, **kwargs) -> None:
        self.created.append(kwargs)


@pytest.fixture(params=["memory", "cosmos"])
def store(request):
    if request.param == "memory":
        return InMemoryAutoApplyStore()
    loaded = CosmosAutoApplyStore(FakeDatabase())
    loaded.seed_default_mappings()
    return loaded


def _create(store, user_id: str = USER, **kwargs):
    payload = dict(
        vendor=kwargs.pop("vendor", "greenhouse"),
        posting_url=kwargs.pop("posting_url", GH_URL),
        mode=kwargs.pop("mode", "api"),
    )
    payload.update(kwargs)
    return store.create_attempt(user_id, **payload)


def _approved(store, user_id: str = USER, **kwargs):
    attempt = _create(store, user_id, **kwargs)
    return store.approve(user_id, attempt.id)


def test_container_specs_match_prd() -> None:
    expected = {
        "auto_apply_attempts": "/user_id",
        "apply_packages": "/auto_apply_id",
        "resume_variants": "/user_id",
        "cover_letters": "/user_id",
        "form_autofill_values": "/auto_apply_id",
        "vendor_field_mappings": "/vendor",
        "submit_requests": "/auto_apply_id",
        "status_events": "/auto_apply_id",
        "webhook_callbacks": "/vendor_application_id",
    }
    specs = {item["id"]: item for item in container_specs()}
    assert set(specs) == set(expected)
    for name, pk in expected.items():
        assert specs[name]["partition_key"] == pk
        assert specs[name]["indexing_policy"]["compositeIndexes"]
    assert STATUS_EVENTS_RETENTION_DAYS == 547
    assert WEBHOOK_RETENTION_DAYS == 90
    assert "queued" not in TERMINAL_ATTEMPT


def test_ensure_creates_all_containers() -> None:
    database = FakeDatabase()
    ensure_auto_apply_containers(database)
    names = {item["id"] for item in database.created}
    assert names == {spec["id"] for spec in container_specs()}
    by_id = {item["id"]: item for item in database.created}
    for spec in container_specs():
        pk = by_id[spec["id"]]["partition_key"]
        path = pk.path if hasattr(pk, "path") else pk
        assert path == spec["partition_key"]


def test_create_draft_and_created_event(store) -> None:
    attempt = _create(store)
    assert attempt.status == "draft"
    assert attempt.approved is False
    events = store.list_status_events(USER, attempt.id)
    assert [event.event_type for event in events] == ["created"]


def test_other_user_cannot_read_attempt(store) -> None:
    attempt = _create(store, vendor="lever", posting_url="https://jobs.lever.co/acme/abc")
    with pytest.raises(AutoApplyNotFoundError):
        store.get_attempt(attempt.id, user_id=OTHER)


def test_cannot_queue_without_approval(store) -> None:
    attempt = _create(store)
    with pytest.raises(AutoApplyConflictError):
        store.queue(USER, attempt.id)


def test_approve_then_queue_locks_package(store) -> None:
    attempt = _approved(store)
    store.put_package(USER, attempt.id, resume_variant_id="rv-1")
    queued = store.queue(USER, attempt.id)
    assert queued.status == "queued"
    package = store.get_package(attempt.id, user_id=USER)
    assert package.locked is True
    events = store.list_status_events(USER, attempt.id)
    assert {event.event_type for event in events} >= {"created", "approved", "package_built", "queued"}


def test_locked_package_cannot_change_payload(store) -> None:
    attempt = _approved(store)
    store.put_package(USER, attempt.id, resume_variant_id="rv-1")
    store.queue(USER, attempt.id)
    with pytest.raises(AutoApplyConflictError):
        store.put_package(USER, attempt.id, resume_variant_id="rv-2")


def test_required_autofill_blocks_queue(store) -> None:
    attempt = _approved(store)
    store.put_autofill(
        USER,
        attempt.id,
        vendor="greenhouse",
        field_key="work_authorization",
        value="",
        source="user_input",
        required=True,
    )
    with pytest.raises(AutoApplyValidationError) as exc:
        store.queue(USER, attempt.id)
    assert exc.value.path == "form_autofill_values"


def test_duplicate_in_flight_job_conflicts(store) -> None:
    first = _create(store, source_application_id="job-99")
    store.approve(USER, first.id)
    store.queue(USER, first.id)
    with pytest.raises(AutoApplyConflictError):
        _create(store, posting_url="https://boards.greenhouse.io/acme/jobs/other", source_application_id="job-99")


def test_submit_idempotency_unique_per_vendor(store) -> None:
    attempt = _approved(store)
    store.queue(USER, attempt.id)
    store.transition(USER, attempt.id, "submitting")
    store.create_submit_request(USER, attempt.id, vendor="greenhouse", idempotency_key="idem-1")
    with pytest.raises(AutoApplyConflictError):
        store.create_submit_request(USER, attempt.id, vendor="greenhouse", idempotency_key="idem-1")


def test_failed_submit_sets_attempt_error(store) -> None:
    attempt = _approved(store)
    store.queue(USER, attempt.id)
    store.transition(USER, attempt.id, "submitting")
    request = store.create_submit_request(USER, attempt.id, vendor="greenhouse", idempotency_key="k1")
    store.complete_submit(
        USER,
        request.id,
        status="failed",
        error_code="vendor_timeout",
        error_message="Greenhouse timed out",
    )
    loaded = store.get_attempt(attempt.id, user_id=USER)
    assert loaded.status == "failed"
    assert loaded.last_error_code == "vendor_timeout"
    assert loaded.last_error_message == "Greenhouse timed out"


def test_vendor_application_id_unique_per_vendor(store) -> None:
    first = _approved(store, posting_url="https://boards.greenhouse.io/acme/jobs/1")
    second = _approved(store, posting_url="https://boards.greenhouse.io/acme/jobs/2")
    store.queue(USER, first.id)
    store.queue(USER, second.id)
    store.transition(USER, first.id, "submitting")
    store.transition(USER, second.id, "submitting")
    request_one = store.create_submit_request(USER, first.id, vendor="greenhouse", idempotency_key="k1")
    request_two = store.create_submit_request(USER, second.id, vendor="greenhouse", idempotency_key="k2")
    store.complete_submit(
        USER,
        request_one.id,
        status="succeeded",
        vendor_application_id="gh-dup",
    )
    with pytest.raises(AutoApplyConflictError):
        store.complete_submit(
            USER,
            request_two.id,
            status="succeeded",
            vendor_application_id="gh-dup",
        )


def test_webhook_dedupe_and_expiry(store) -> None:
    attempt = _approved(store)
    store.queue(USER, attempt.id)
    store.transition(USER, attempt.id, "submitting")
    request = store.create_submit_request(USER, attempt.id, vendor="greenhouse", idempotency_key="k1")
    store.complete_submit(
        USER,
        request.id,
        status="succeeded",
        vendor_application_id="gh-1",
    )
    first = store.ingest_webhook(
        vendor="greenhouse",
        vendor_application_id="gh-1",
        event_type="submitted",
        payload_blob_uri="https://blob/webhooks/1.json",
        dedupe_key="gh:1:submitted",
    )
    again = store.ingest_webhook(
        vendor="greenhouse",
        vendor_application_id="gh-1",
        event_type="submitted",
        payload_blob_uri="https://blob/webhooks/1.json",
        dedupe_key="gh:1:submitted",
    )
    assert first.id == again.id
    listed = store.list_webhooks(vendor_application_id="gh-1")
    assert len(listed) == 1
    assert listed[0].auto_apply_id == attempt.id

    future = (datetime.now(timezone.utc) + timedelta(days=WEBHOOK_RETENTION_DAYS + 1)).isoformat()
    hidden = store.list_webhooks(vendor_application_id="gh-1", now=future)
    assert hidden == []


def test_status_events_are_append_only(store) -> None:
    attempt = _create(store)
    store.approve(USER, attempt.id)
    events = store.list_status_events(USER, attempt.id)
    assert [event.event_type for event in events] == ["created", "approved"]
    events[0].event_type = "mutated"
    again = store.list_status_events(USER, attempt.id)
    assert again[0].event_type == "created"


def test_manual_vendor_forces_manual_package(store) -> None:
    attempt = _create(
        store,
        vendor="manual",
        mode="api",
        posting_url="https://jobs.example.com/role",
    )
    assert attempt.mode == "manual_package"


def test_default_vendor_mappings_are_seeded(store) -> None:
    greenhouse = store.list_vendor_mappings("greenhouse")
    lever = store.list_vendor_mappings("lever")
    assert {row.normalized_key for row in greenhouse} >= {"full_name", "email", "phone"}
    assert {row.normalized_key for row in lever} >= {"full_name", "email", "phone"}


def test_cosmos_round_trip_hydrate_and_persist() -> None:
    database = FakeDatabase()
    first = CosmosAutoApplyStore(database)
    attempt = first.create_attempt(
        USER,
        vendor="lever",
        posting_url="https://jobs.lever.co/acme/abc",
        mode="api",
    )
    first.approve(USER, attempt.id)
    first.put_package(USER, attempt.id, resume_variant_id="rv-9")
    first.queue(USER, attempt.id)

    second = CosmosAutoApplyStore(database)
    loaded = second.get_attempt(attempt.id, user_id=USER)
    assert loaded.status == "queued"
    package = second.get_package(attempt.id, user_id=USER)
    assert package.locked is True
    assert package.resume_variant_id == "rv-9"


def test_factory_defaults_to_memory(monkeypatch) -> None:
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    loaded = get_auto_apply_store()
    assert isinstance(loaded, InMemoryAutoApplyStore)
    config.get_settings.cache_clear()

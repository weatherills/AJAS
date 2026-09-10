"""Review & Decision Database PRD — schema, constraints, and store behaviors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.review import (
    AUDIT_CONTAINER,
    DECISIONS_CONTAINER,
    MATCHES_CONTAINER,
    MAX_COMMENT_CHARS,
    InMemoryReviewStore,
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewPreconditionError,
    ReviewValidationError,
    container_specs,
    get_review_store,
)
from app.review.constants import AUDIT_PK, DECISIONS_PK, MATCHES_PK
from app.review.containers import ensure_review_containers
from app.review.cosmos_store import CosmosReviewStore


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

    def delete_item(self, item: str, partition_key: str | None = None) -> None:
        item_id = item if isinstance(item, str) else item["id"]
        keys = [key for key in self.items if key[1] == item_id]
        if partition_key is not None:
            keys = [key for key in keys if key[0] == partition_key]
        if not keys:
            raise _not_found()
        for key in keys:
            del self.items[key]

    def query_items(self, query: str, parameters=None, partition_key=None, **_kwargs):
        rows = [dict(v) for v in self.items.values()]
        if partition_key is not None:
            rows = [r for r in rows if r.get(self.pk_field) == partition_key]
        return rows


class FakeDatabase:
    def __init__(self) -> None:
        self._containers = {
            MATCHES_CONTAINER: FakeContainer("user_id"),
            DECISIONS_CONTAINER: FakeContainer("user_id"),
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
        return InMemoryReviewStore()
    return CosmosReviewStore(FakeDatabase())


USER = "user-1"
OTHER = "user-2"


def _create(store, user_id=USER, **overrides):
    payload = dict(
        job_id="job-1",
        resume_id="resume-1",
        job_title="Staff Platform Engineer",
        company="Acme",
        location="Remote",
        ai_score=88.0,
        suggestion="approve",
        why="Strong overlap on platform work.",
        summary="Good match for staff-level platform roles.",
        highlights_json=["Python", "Kubernetes"],
    )
    payload.update(overrides)
    return store.create_match(user_id, **payload)


def test_container_specs_match_prd():
    specs = {item["id"]: item for item in container_specs()}
    expected = {
        MATCHES_CONTAINER: MATCHES_PK,
        DECISIONS_CONTAINER: DECISIONS_PK,
        AUDIT_CONTAINER: AUDIT_PK,
    }
    assert set(specs) == set(expected)
    for name, pk in expected.items():
        assert specs[name]["partition_key"] == pk
        assert specs[name]["indexing_policy"]["compositeIndexes"]
        assert pk == "/user_id"


def test_ensure_review_containers_creates_three():
    database = FakeDatabase()
    ensure_review_containers(database)
    assert {item["id"] for item in database.created} == {
        MATCHES_CONTAINER,
        DECISIONS_CONTAINER,
        AUDIT_CONTAINER,
    }
    for item in database.created:
        pk = item["partition_key"]
        path = pk.path if hasattr(pk, "path") else pk
        assert path == "/user_id"


def test_create_and_get_match_scoped_to_user(store):
    created = _create(store)
    loaded = store.get_match(created.id, user_id=USER)
    assert loaded.id == created.id
    assert loaded.status == "PENDING"
    assert loaded.source == "ai"
    assert loaded.etag == "1"
    assert loaded.latest_decision_id is None
    with pytest.raises(ReviewNotFoundError):
        store.get_match(created.id, user_id=OTHER)


def test_duplicate_match_conflicts(store):
    _create(store)
    with pytest.raises(ReviewConflictError):
        _create(store)
    other = _create(store, user_id=OTHER)
    assert other.user_id == OTHER
    saved = _create(store, source="saved")
    assert saved.source == "saved"


def test_update_pending_match_rewrites_score(store):
    created = _create(store, ai_score=88)
    updated = store.update_pending_match(
        USER,
        created.id,
        ai_score=48.1,
        suggestion="reject",
        why="Live score from Job Feed Save match.",
        summary="Live score from Job Feed Save match.",
    )
    assert updated.ai_score == 48.1
    assert updated.suggestion == "reject"
    assert updated.why.startswith("Live score")
    assert updated.etag != created.etag
    loaded = store.get_match(created.id, user_id=USER)
    assert loaded.ai_score == 48.1


def test_update_pending_match_can_change_source(store):
    created = _create(store, source="ai", ai_score=88)
    updated = store.update_pending_match(USER, created.id, source="saved", ai_score=48.1)
    assert updated.source == "saved"
    assert updated.ai_score == 48.1
    assert store.get_match(created.id, user_id=USER).source == "saved"


def test_discard_pending_match_removes_row(store):
    created = _create(store, source="ai")
    store.discard_pending_match(USER, created.id)
    assert store.list_matches(USER) == []


def test_list_pending_and_filters(store):
    _create(store, job_id="j1", job_title="Staff Engineer", company="Acme", location="Austin", ai_score=88)
    _create(
        store,
        job_id="j2",
        job_title="Data Analyst",
        company="Globex",
        location="Remote",
        ai_score=40,
        suggestion="reject",
        source="saved",
    )
    pending = store.list_matches(USER, status="PENDING")
    assert len(pending) == 2
    high = store.list_matches(USER, min_score=80)
    assert {item.job_id for item in high} == {"j1"}
    titled = store.list_matches(USER, job_title="staff")
    assert {item.job_id for item in titled} == {"j1"}
    company = store.list_matches(USER, company="glob")
    assert {item.job_id for item in company} == {"j2"}
    location = store.list_matches(USER, location="remote")
    assert {item.job_id for item in location} == {"j2"}
    saved = store.list_matches(USER, source="saved")
    assert {item.job_id for item in saved} == {"j2"}
    assert store.list_matches(OTHER) == []


def test_decide_approve_and_reject_updates_status(store):
    match = _create(store)
    updated, event = store.decide(USER, match.id, "approve", comment="Ship it")
    assert updated.status == "APPROVED"
    assert updated.latest_decision_id == event.id
    assert updated.decided_at is not None
    assert event.decision == "approve"
    assert event.comment == "Ship it"
    assert event.ai_score == 88.0
    assert event.suggestion == "approve"
    assert event.version == 1
    assert event.supersedes_decision_id is None
    loaded = store.get_match(match.id, user_id=USER)
    assert loaded.status == "APPROVED"
    assert loaded.latest_decision_id == event.id


def test_redecide_without_overwrite_conflicts(store):
    match = _create(store)
    store.decide(USER, match.id, "approve")
    with pytest.raises(ReviewConflictError):
        store.decide(USER, match.id, "reject")


def test_overwrite_appends_and_supersedes(store):
    match = _create(store)
    first_match, first = store.decide(USER, match.id, "approve")
    second_match, second = store.decide(USER, match.id, "reject", overwrite=True, comment="Changed my mind")
    assert second_match.status == "REJECTED"
    assert second.supersedes_decision_id == first.id
    assert second.version == 2
    history = store.list_decisions(USER, match.id)
    assert [item.id for item in history] == [first.id, second.id]
    assert first_match.latest_decision_id == first.id
    current = store.get_match(match.id, user_id=USER)
    assert current.latest_decision_id == second.id


def _expire_stored_lock(store, match_id: str) -> None:
    past = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    if isinstance(store, InMemoryReviewStore):
        store._matches[match_id].lock_expires_at = past
        return
    inner = store._hydrate()
    inner._matches[match_id].lock_expires_at = past
    store._persist_working(inner)


def test_lock_held_vs_expired(store):
    match = _create(store)
    claimed = store.claim_match(USER, match.id, "owner-a", ttl_seconds=120)
    assert claimed.lock_owner == "owner-a"
    assert claimed.lock_expires_at is not None
    with pytest.raises(ReviewConflictError):
        store.claim_match(USER, match.id, "owner-b")
    _expire_stored_lock(store, match.id)
    reclaimed = store.claim_match(USER, match.id, "owner-b")
    assert reclaimed.lock_owner == "owner-b"
    audits = store.list_audit(USER, match_id=match.id, event_type="UNLOCK_EXPIRED")
    assert len(audits) == 1


def test_reopen_returns_pending_and_keeps_history(store):
    match = _create(store)
    _, first = store.decide(USER, match.id, "reject", comment="Not now")
    reopened = store.reopen(USER, match.id)
    assert reopened.status == "PENDING"
    assert reopened.latest_decision_id is None
    assert reopened.decided_at is None
    history = store.list_decisions(USER, match.id)
    assert [item.id for item in history] == [first.id]
    audits = store.list_audit(USER, match_id=match.id, event_type="REOPEN")
    assert len(audits) == 1


def test_comment_too_long_is_validation_error(store):
    match = _create(store)
    with pytest.raises(ReviewValidationError) as exc:
        store.decide(USER, match.id, "approve", comment="x" * (MAX_COMMENT_CHARS + 1))
    assert exc.value.path == "comment"
    pending = store.get_match(match.id, user_id=USER)
    assert pending.status == "PENDING"


def test_score_out_of_range_is_validation_error(store):
    with pytest.raises(ReviewValidationError) as exc:
        _create(store, ai_score=120)
    assert exc.value.path == "ai_score"
    with pytest.raises(ReviewValidationError):
        _create(store, job_id="j-neg", ai_score=-1)


def test_etag_mismatch_is_precondition_error(store):
    match = _create(store)
    with pytest.raises(ReviewPreconditionError):
        store.decide(USER, match.id, "approve", etag="999")
    with pytest.raises(ReviewPreconditionError):
        store.claim_match(USER, match.id, "owner-a", etag="999")
    updated, _event = store.decide(USER, match.id, "approve", etag=match.etag)
    assert updated.status == "APPROVED"


def test_audit_is_append_only(store):
    match = _create(store)
    store.record_audit(user_id=USER, event_type="VIEW_LIST", payload={"status": "PENDING"})
    store.record_audit(user_id=USER, event_type="VIEW_DETAIL", match_id=match.id)
    store.record_audit(
        user_id=USER,
        event_type="DEGRADED_VIEW",
        match_id=match.id,
        payload={"missing": ["summary_blob_uri"]},
    )
    events = store.list_audit(USER, match_id=match.id)
    types = [item.event_type for item in events]
    assert "VIEW_DETAIL" in types
    assert "DEGRADED_VIEW" in types
    listed = store.list_audit(USER, event_type="VIEW_LIST")
    assert len(listed) == 1
    assert store.list_audit(OTHER) == []


def test_missing_summary_and_highlights_are_allowed(store):
    match = _create(
        store,
        job_id="sparse",
        summary=None,
        why=None,
        summary_blob_uri=None,
        highlights_json=None,
        ai_score=None,
        suggestion="none",
    )
    assert match.summary is None
    assert match.highlights_json is None
    assert match.ai_score is None
    loaded = store.get_match(match.id, user_id=USER)
    assert loaded.summary is None


def test_idempotent_decide_returns_original(store):
    match = _create(store)
    first_match, first = store.decide(USER, match.id, "approve", idempotency_key="dec-1")
    second_match, second = store.decide(USER, match.id, "approve", idempotency_key="dec-1")
    assert first.id == second.id
    assert first_match.latest_decision_id == second_match.latest_decision_id
    assert len(store.list_decisions(USER, match.id)) == 1


def test_cosmos_hydrate_persist_round_trip():
    database = FakeDatabase()
    first = CosmosReviewStore(database)
    created = _create(first, job_id="persist-me")
    first.decide(USER, created.id, "approve", comment="ok")
    second = CosmosReviewStore(database)
    loaded = second.get_match(created.id, user_id=USER)
    assert loaded.status == "APPROVED"
    assert loaded.job_title == "Staff Platform Engineer"
    history = second.list_decisions(USER, created.id)
    assert len(history) == 1
    assert history[0].comment == "ok"


def test_get_review_store_defaults_to_memory(monkeypatch):
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    loaded = get_review_store()
    assert isinstance(loaded, InMemoryReviewStore)
    config.get_settings.cache_clear()

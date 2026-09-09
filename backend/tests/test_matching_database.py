"""Matching Database PRD — schema, constraints, and store behaviors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.matching import (
    DEFAULT_MODEL_ID,
    DEFAULT_THRESHOLD_PCT,
    InMemoryMatchingStore,
    MatchingConflictError,
    MatchingNotFoundError,
    MatchingValidationError,
    container_specs,
    get_matching_store,
    overall_score_pct,
)
from app.matching.constants import (
    EXPLANATIONS_CONTAINER,
    EXPLANATIONS_PK,
    HISTORY_CONTAINER,
    HISTORY_PK,
    MODELS_CONTAINER,
    MODELS_PK,
    PREFS_CONTAINER,
    PREFS_PK,
    RUNS_CONTAINER,
    RUNS_PK,
)
from app.matching.containers import ensure_matching_containers
from app.matching.cosmos_store import CosmosMatchingStore


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
            RUNS_CONTAINER: FakeContainer("user_id"),
            EXPLANATIONS_CONTAINER: FakeContainer("match_id"),
            PREFS_CONTAINER: FakeContainer("user_id"),
            HISTORY_CONTAINER: FakeContainer("user_id"),
            MODELS_CONTAINER: FakeContainer("id"),
        }
        self.created: list[dict] = []

    def get_container_client(self, name: str) -> FakeContainer:
        return self._containers[name]

    def create_container_if_not_exists(self, **kwargs) -> None:
        self.created.append(kwargs)


@pytest.fixture(params=["memory", "cosmos"])
def store(request):
    if request.param == "memory":
        return InMemoryMatchingStore()
    cosmos = CosmosMatchingStore(FakeDatabase())
    cosmos.seed_default_model()
    return cosmos


USER = "user-1"
OTHER = "user-2"


def test_container_specs_match_prd():
    specs = {item["id"]: item for item in container_specs()}
    expected = {
        RUNS_CONTAINER: RUNS_PK,
        EXPLANATIONS_CONTAINER: EXPLANATIONS_PK,
        PREFS_CONTAINER: PREFS_PK,
        HISTORY_CONTAINER: HISTORY_PK,
        MODELS_CONTAINER: MODELS_PK,
    }
    assert set(specs) == set(expected)
    for name, pk in expected.items():
        assert specs[name]["partition_key"] == pk
        assert specs[name]["indexing_policy"]["compositeIndexes"]


def test_ensure_matching_containers_creates_five():
    database = FakeDatabase()
    ensure_matching_containers(database)
    assert {item["id"] for item in database.created} == set(
        [RUNS_CONTAINER, EXPLANATIONS_CONTAINER, PREFS_CONTAINER, HISTORY_CONTAINER, MODELS_CONTAINER]
    )


def test_overall_score_uses_formula_weights():
    assert overall_score_pct(1.0, 1.0) == 100
    assert overall_score_pct(1.0, 0.0) == 40
    assert overall_score_pct(0.0, 1.0) == 60
    assert overall_score_pct(0.5, 0.5) == 50


def test_seeded_model_and_default_prefs(store):
    model = store.get_model(DEFAULT_MODEL_ID)
    assert model.formula_version == "weighted-0.4-0.6"
    prefs = store.get_or_create_prefs(USER)
    assert prefs.threshold_pct == DEFAULT_THRESHOLD_PCT
    assert prefs.save_all_matches is False
    again = store.get_or_create_prefs(USER)
    assert again.version == prefs.version == 1


def test_pref_update_writes_immutable_history(store):
    store.get_or_create_prefs(USER)
    updated = store.update_prefs(USER, threshold_pct=80, save_all_matches=True)
    assert updated.threshold_pct == 80
    assert updated.save_all_matches is True
    assert updated.version == 2
    history = store.list_pref_history(USER)
    assert len(history) == 1
    assert history[0].threshold_pct == DEFAULT_THRESHOLD_PCT
    assert history[0].save_all_matches is False
    with pytest.raises(MatchingValidationError):
        store.update_prefs(USER, threshold_pct=101)


def test_create_run_computes_threshold_and_save_decision(store):
    run = store.create_run(
        USER,
        resume_id="resume-1",
        job_id="job-1",
        keyword_raw=0.9,
        semantic_raw=0.9,
    )
    assert run.overall_score_pct == 90
    assert run.threshold_used == 70
    assert run.meets_threshold is True
    assert run.decision_saved is True
    below = store.create_run(
        USER,
        resume_id="resume-1",
        job_id="job-2",
        keyword_raw=0.2,
        semantic_raw=0.2,
    )
    assert below.overall_score_pct == 20
    assert below.meets_threshold is False
    assert below.decision_saved is False
    saved = store.list_runs(USER, saved_only=True)
    assert {item.id for item in saved} == {run.id}


def test_threshold_override_and_save_all(store):
    store.update_prefs(USER, save_all_matches=True)
    run = store.create_run(
        USER,
        resume_id="r",
        job_id="j",
        keyword_raw=0.2,
        semantic_raw=0.2,
        threshold_override=90,
    )
    assert run.threshold_used == 90
    assert run.meets_threshold is False
    assert run.decision_saved is True


def test_missing_prefs_use_default_without_caller_creating_them():
    store = InMemoryMatchingStore()
    run = store.create_run("fresh-user", resume_hash="abc", job_hash="def", keyword_raw=1.0, semantic_raw=1.0)
    assert run.threshold_used == 70
    assert store.get_or_create_prefs("fresh-user").threshold_pct == 70


def test_idempotency_conflict(store):
    kwargs = dict(resume_id="r1", job_id="j1", keyword_raw=0.8, semantic_raw=0.7)
    store.create_run(USER, **kwargs)
    with pytest.raises(MatchingConflictError):
        store.create_run(USER, **kwargs)
    other = store.create_run(OTHER, **kwargs)
    assert other.user_id == OTHER


def test_error_run_is_not_saved(store):
    run = store.create_run(
        USER,
        resume_id="r",
        job_id="j",
        keyword_raw=1.0,
        semantic_raw=1.0,
        run_status="error",
        error_message="embeddings failed",
    )
    assert run.run_status == "error"
    assert run.decision_saved is False
    assert run.meets_threshold is False
    assert run.overall_score_pct == 0


def test_explanation_is_one_to_one(store):
    run = store.create_run(USER, resume_id="r", job_id="j", keyword_raw=0.8, semantic_raw=0.8)
    explained = store.put_explanation(run.id, summary="Strong skills overlap.", highlights=["Python"], gaps=["Go"])
    loaded = store.get_explanation(run.id)
    assert loaded.id == explained.id
    assert store.get_run(run.id).explanation_summary.startswith("Strong")
    with pytest.raises(MatchingConflictError):
        store.put_explanation(run.id, summary="again")
    with pytest.raises(MatchingNotFoundError):
        store.get_run(run.id, user_id=OTHER)


def test_new_model_does_not_rewrite_old_runs(store):
    first = store.create_run(USER, resume_id="r", job_id="j", keyword_raw=1.0, semantic_raw=0.0)
    store.register_model(
        id="matching-v2",
        ai_service="azure_openai",
        scorer_model="text-embedding-3-large",
        scorer_model_version="1",
        formula_version="weighted-0.5-0.5",
        keyword_weight=0.5,
        semantic_weight=0.5,
        normalization_method="clamp-0-1",
        prompt_version="explain-v2",
    )
    second = store.create_run(
        USER, resume_id="r", job_id="j2", keyword_raw=1.0, semantic_raw=0.0, model_version_id="matching-v2"
    )
    assert store.get_run(first.id).model_version_id == DEFAULT_MODEL_ID
    assert store.get_run(first.id).overall_score_pct == 40
    assert second.model_version_id == "matching-v2"
    assert second.overall_score_pct == 50


def test_expired_runs_are_hidden_from_lists(store):
    run = store.create_run(USER, resume_id="r", job_id="j", keyword_raw=0.9, semantic_raw=0.9)
    future = (datetime.now(timezone.utc) + timedelta(days=548)).isoformat().replace("+00:00", "Z")
    assert store.list_runs(USER, now=future) == []
    assert store.list_runs(USER, include_expired=True, now=future)[0].id == run.id


def test_rejects_invalid_scores_and_missing_refs(store):
    with pytest.raises(MatchingValidationError):
        store.create_run(USER, resume_id="r", job_id="j", keyword_raw=1.2)
    with pytest.raises(MatchingValidationError):
        store.create_run(USER, job_id="j", keyword_raw=0.1, semantic_raw=0.1)
    with pytest.raises(MatchingNotFoundError):
        store.create_run(USER, resume_id="r", job_id="j", model_version_id="nope")


def test_get_matching_store_defaults_to_memory(monkeypatch):
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    loaded = get_matching_store()
    assert isinstance(loaded, InMemoryMatchingStore)
    assert get_matching_store() is loaded
    config.get_settings.cache_clear()

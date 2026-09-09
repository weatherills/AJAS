"""Cosmos DB implementation of MatchingStore."""

from __future__ import annotations

from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.matching.constants import (
    EXPLANATIONS_CONTAINER,
    HISTORY_CONTAINER,
    MODELS_CONTAINER,
    PREFS_CONTAINER,
    RUNS_CONTAINER,
)
from app.matching.memory import InMemoryMatchingStore
from app.matching.models import (
    MatchExplanation,
    MatchRun,
    ModelRegistry,
    UserMatchPrefHistory,
    UserMatchPrefs,
)


class CosmosMatchingStore:
    def __init__(self, database: Any) -> None:
        self._runs = database.get_container_client(RUNS_CONTAINER)
        self._explanations = database.get_container_client(EXPLANATIONS_CONTAINER)
        self._prefs = database.get_container_client(PREFS_CONTAINER)
        self._history = database.get_container_client(HISTORY_CONTAINER)
        self._models = database.get_container_client(MODELS_CONTAINER)

    def seed_default_model(self) -> ModelRegistry:
        working = self._hydrate()
        saved = working.seed_default_model()
        self._persist_working(working)
        return saved

    def register_model(self, **kwargs: Any) -> ModelRegistry:
        working = self._hydrate()
        saved = working.register_model(**kwargs)
        self._persist_working(working)
        return saved

    def get_model(self, model_id: str) -> ModelRegistry:
        return self._hydrate().get_model(model_id)

    def list_models(self) -> list[ModelRegistry]:
        return self._hydrate().list_models()

    def get_or_create_prefs(self, user_id: str) -> UserMatchPrefs:
        working = self._hydrate()
        saved = working.get_or_create_prefs(user_id)
        self._persist_working(working)
        return saved

    def update_prefs(self, user_id: str, **kwargs: Any) -> UserMatchPrefs:
        working = self._hydrate()
        saved = working.update_prefs(user_id, **kwargs)
        self._persist_working(working)
        return saved

    def list_pref_history(self, user_id: str) -> list[UserMatchPrefHistory]:
        return self._hydrate().list_pref_history(user_id)

    def create_run(self, user_id: str, **kwargs: Any) -> MatchRun:
        working = self._hydrate()
        saved = working.create_run(user_id, **kwargs)
        self._persist_working(working)
        return saved

    def get_run(self, run_id: str, *, user_id: str | None = None) -> MatchRun:
        return self._hydrate().get_run(run_id, user_id=user_id)

    def list_runs(self, user_id: str, **kwargs: Any) -> list[MatchRun]:
        return self._hydrate().list_runs(user_id, **kwargs)

    def put_explanation(self, match_id: str, **kwargs: Any) -> MatchExplanation:
        working = self._hydrate()
        saved = working.put_explanation(match_id, **kwargs)
        self._persist_working(working)
        return saved

    def get_explanation(self, match_id: str) -> MatchExplanation:
        return self._hydrate().get_explanation(match_id)

    def _all_items(self, client: Any) -> list[dict]:
        try:
            return list(client.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))
        except TypeError:
            return list(client.query_items(query="SELECT * FROM c"))

    def _hydrate(self) -> InMemoryMatchingStore:
        working = InMemoryMatchingStore(seed=False)
        working._models = {row.id: row for row in (ModelRegistry.model_validate(i) for i in self._all_items(self._models))}
        working._prefs = {row.id: row for row in (UserMatchPrefs.model_validate(i) for i in self._all_items(self._prefs))}
        working._history = {
            row.id: row for row in (UserMatchPrefHistory.model_validate(i) for i in self._all_items(self._history))
        }
        working._runs = {row.id: row for row in (MatchRun.model_validate(i) for i in self._all_items(self._runs))}
        working._explanations = {
            row.id: row for row in (MatchExplanation.model_validate(i) for i in self._all_items(self._explanations))
        }
        return working

    def _upsert(self, client: Any, payload: dict) -> None:
        try:
            client.replace_item(item=payload["id"], body=payload)
        except CosmosResourceNotFoundError:
            client.create_item(body=payload)

    def _persist_working(self, working: InMemoryMatchingStore) -> None:
        for row in working._models.values():
            self._upsert(self._models, row.model_dump())
        for row in working._prefs.values():
            self._upsert(self._prefs, row.model_dump())
        for row in working._history.values():
            self._upsert(self._history, row.model_dump())
        for row in working._runs.values():
            self._upsert(self._runs, row.model_dump())
        for row in working._explanations.values():
            self._upsert(self._explanations, row.model_dump())

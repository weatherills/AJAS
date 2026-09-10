"""Cosmos DB implementation of LearningStore."""

from __future__ import annotations

from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.learning.constants import (
    CONFIGS_CONTAINER,
    DECISIONS_CONTAINER,
    EVENTS_CONTAINER,
    METRICS_CONTAINER,
    PARAMS_CONTAINER,
    RECS_CONTAINER,
)
from app.learning.memory import InMemoryLearningStore
from app.learning.models import (
    DecisionLog,
    MetricsSnapshot,
    ModelParams,
    Recommendation,
    WeightConfig,
    WeightTuningEvent,
)


class CosmosLearningStore:
    def __init__(self, database: Any) -> None:
        self._recs = database.get_container_client(RECS_CONTAINER)
        self._decisions = database.get_container_client(DECISIONS_CONTAINER)
        self._params = database.get_container_client(PARAMS_CONTAINER)
        self._configs = database.get_container_client(CONFIGS_CONTAINER)
        self._events = database.get_container_client(EVENTS_CONTAINER)
        self._metrics = database.get_container_client(METRICS_CONTAINER)

    def __getattr__(self, name: str):
        def wrapper(*args, **kwargs):
            working = self._hydrate()
            result = getattr(working, name)(*args, **kwargs)
            writes = not (
                name.startswith("get_")
                or name.startswith("list_")
                or name in {"active_global_config", "users_with_decisions"}
            )
            if writes:
                self._persist_working(working)
            return result

        if name.startswith("_"):
            raise AttributeError(name)
        return wrapper

    def _all_items(self, client: Any) -> list[dict]:
        try:
            return list(client.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))
        except TypeError:
            return list(client.query_items(query="SELECT * FROM c"))

    def _hydrate(self) -> InMemoryLearningStore:
        working = InMemoryLearningStore(seed=False)
        working._recs = {row.id: row for row in (Recommendation.model_validate(i) for i in self._all_items(self._recs))}
        decisions = [DecisionLog.model_validate(i) for i in self._all_items(self._decisions)]
        working._decisions = {row.id: row for row in decisions}
        working._by_rec = {(row.user_id, row.recommendation_id): row.id for row in decisions}
        working._by_idem = {(row.user_id, row.idempotency_key): row.id for row in decisions}
        params = [ModelParams.model_validate(i) for i in self._all_items(self._params)]
        working._params = {row.user_id: row for row in params}
        working._configs = {
            row.id: row for row in (WeightConfig.model_validate(i) for i in self._all_items(self._configs))
        } or working._configs
        working._events = {
            row.id: row for row in (WeightTuningEvent.model_validate(i) for i in self._all_items(self._events))
        }
        working._metrics = {
            row.id: row for row in (MetricsSnapshot.model_validate(i) for i in self._all_items(self._metrics))
        }
        return working

    def _upsert(self, client: Any, payload: dict) -> None:
        try:
            client.replace_item(item=payload["id"], body=payload)
        except CosmosResourceNotFoundError:
            client.create_item(body=payload)

    def _persist_working(self, working: InMemoryLearningStore) -> None:
        for row in working._recs.values():
            self._upsert(self._recs, row.model_dump())
        for row in working._decisions.values():
            self._upsert(self._decisions, row.model_dump())
        for row in working._params.values():
            self._upsert(self._params, row.model_dump())
        for row in working._configs.values():
            self._upsert(self._configs, row.model_dump())
        for row in working._events.values():
            self._upsert(self._events, row.model_dump())
        for row in working._metrics.values():
            self._upsert(self._metrics, row.model_dump())

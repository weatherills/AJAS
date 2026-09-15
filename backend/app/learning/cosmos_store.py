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

    def delete_user_data(self, user_id: str) -> None:
        working = self._hydrate()
        recs = [row.id for row in working.list_recommendations(user_id)]
        decisions = [row.id for row in working.list_decisions(user_id)]
        events = [row.id for row in working.list_events(user_id)]
        metrics = [row.id for row in working.list_metrics(scope_ref=user_id)]
        working.delete_user_data(user_id)
        for rec_id in recs:
            self._delete_item(self._recs, rec_id, user_id)
        for decision_id in decisions:
            self._delete_item(self._decisions, decision_id, user_id)
        self._delete_item(self._params, user_id, user_id)
        for event_id in events:
            self._delete_item(self._events, event_id, event_id)
        for metric_id in metrics:
            self._delete_item(self._metrics, metric_id, user_id)

    def _delete_item(self, client: Any, item_id: str, partition_key: str) -> None:
        try:
            client.delete_item(item=item_id, partition_key=partition_key)
        except CosmosResourceNotFoundError:
            return
        except Exception:
            try:
                client.delete_item(item=item_id, partition_key=item_id)
            except Exception:
                return

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

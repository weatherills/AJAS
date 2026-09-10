"""Learning store protocol and factory."""

from __future__ import annotations

from typing import Protocol

from app.learning.models import (
    DecisionLog,
    MetricsSnapshot,
    ModelParams,
    Recommendation,
    WeightConfig,
    WeightTuningEvent,
)


class LearningStore(Protocol):
    def upsert_recommendation(self, rec: Recommendation) -> Recommendation: ...

    def get_recommendation(self, rec_id: str) -> Recommendation: ...

    def list_recommendations(self, user_id: str) -> list[Recommendation]: ...

    def put_decision(self, row: DecisionLog) -> DecisionLog: ...

    def get_decision(self, decision_id: str) -> DecisionLog: ...

    def get_decision_by_rec(self, user_id: str, recommendation_id: str) -> DecisionLog | None: ...

    def get_by_idempotency(self, user_id: str, key: str) -> DecisionLog | None: ...

    def list_decisions(self, user_id: str) -> list[DecisionLog]: ...

    def get_or_create_params(self, user_id: str) -> ModelParams: ...

    def put_params(self, row: ModelParams) -> ModelParams: ...

    def put_config(self, row: WeightConfig) -> WeightConfig: ...

    def get_config(self, config_id: str) -> WeightConfig: ...

    def active_global_config(self) -> WeightConfig: ...

    def put_event(self, row: WeightTuningEvent) -> WeightTuningEvent: ...

    def list_events(self, user_id: str | None = None) -> list[WeightTuningEvent]: ...

    def put_metrics(self, row: MetricsSnapshot) -> MetricsSnapshot: ...

    def list_metrics(self, *, scope_ref: str | None = None) -> list[MetricsSnapshot]: ...

    def put_blob(self, path: str, payload: dict) -> None: ...

    def seed_demo(self, user_id: str) -> None: ...

    def users_with_decisions(self) -> list[str]: ...


_store: LearningStore | None = None


def get_learning_store() -> LearningStore:
    global _store
    if _store is not None:
        return _store
    from app.config import get_settings
    from app.learning.memory import InMemoryLearningStore

    settings = get_settings()
    if not settings.cosmos_connection_string:
        _store = InMemoryLearningStore(seed=True)
        return _store
    from app.learning.cosmos_store import CosmosLearningStore
    from app.storage.cosmos import get_database

    _store = CosmosLearningStore(get_database())
    return _store


def set_learning_store(store: LearningStore | None) -> None:
    global _store
    _store = store

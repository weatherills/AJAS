"""Matching store protocol and factory."""

from __future__ import annotations

from typing import Protocol

from app.matching.models import (
    MatchExplanation,
    MatchRun,
    ModelRegistry,
    UserMatchPrefHistory,
    UserMatchPrefs,
)


class MatchingStore(Protocol):
    def seed_default_model(self) -> ModelRegistry: ...

    def register_model(self, **kwargs) -> ModelRegistry: ...

    def get_model(self, model_id: str) -> ModelRegistry: ...

    def list_models(self) -> list[ModelRegistry]: ...

    def get_or_create_prefs(self, user_id: str) -> UserMatchPrefs: ...

    def update_prefs(
        self,
        user_id: str,
        *,
        threshold_pct: int | None = None,
        save_all_matches: bool | None = None,
    ) -> UserMatchPrefs: ...

    def list_pref_history(self, user_id: str) -> list[UserMatchPrefHistory]: ...

    def create_run(self, user_id: str, **kwargs) -> MatchRun: ...

    def get_run(self, run_id: str, *, user_id: str | None = None) -> MatchRun: ...

    def list_runs(self, user_id: str, **kwargs) -> list[MatchRun]: ...

    def put_explanation(self, match_id: str, **kwargs) -> MatchExplanation: ...

    def get_explanation(self, match_id: str) -> MatchExplanation: ...


_store: MatchingStore | None = None


def get_matching_store() -> MatchingStore:
    """Return Cosmos when configured, otherwise a process-wide in-memory store."""
    global _store
    if _store is not None:
        return _store
    from app.config import get_settings
    from app.matching.memory import InMemoryMatchingStore

    settings = get_settings()
    if not settings.cosmos_connection_string:
        _store = InMemoryMatchingStore()
        return _store
    from app.matching.cosmos_store import CosmosMatchingStore
    from app.storage.cosmos import get_database

    _store = CosmosMatchingStore(get_database())
    return _store

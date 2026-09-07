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


def get_matching_store() -> MatchingStore:
    from app.config import get_settings
    from app.matching.memory import InMemoryMatchingStore

    settings = get_settings()
    if not settings.cosmos_connection_string:
        return InMemoryMatchingStore()
    from app.matching.cosmos_store import CosmosMatchingStore
    from app.storage.cosmos import get_database

    return CosmosMatchingStore(get_database())

"""Review store protocol and factory."""

from __future__ import annotations

from typing import Any, Protocol

from app.review.models import AuditEvent, DecisionEvent, ReviewMatch


class ReviewStore(Protocol):
    def create_match(self, user_id: str, **kwargs: Any) -> ReviewMatch: ...

    def get_match(self, match_id: str, *, user_id: str) -> ReviewMatch: ...

    def list_matches(self, user_id: str, **kwargs: Any) -> list[ReviewMatch]: ...

    def claim_match(self, user_id: str, match_id: str, owner: str, **kwargs: Any) -> ReviewMatch: ...

    def release_lock(self, user_id: str, match_id: str, owner: str) -> ReviewMatch: ...

    def decide(
        self, user_id: str, match_id: str, decision: str, **kwargs: Any
    ) -> tuple[ReviewMatch, DecisionEvent]: ...

    def reopen(self, user_id: str, match_id: str) -> ReviewMatch: ...

    def list_decisions(self, user_id: str, match_id: str | None = None) -> list[DecisionEvent]: ...

    def record_audit(self, **kwargs: Any) -> AuditEvent: ...

    def list_audit(self, user_id: str, **kwargs: Any) -> list[AuditEvent]: ...


def get_review_store() -> ReviewStore:
    from app.config import get_settings
    from app.review.memory import InMemoryReviewStore

    settings = get_settings()
    if not settings.cosmos_connection_string:
        return InMemoryReviewStore()
    from app.review.cosmos_store import CosmosReviewStore
    from app.storage.cosmos import get_database

    return CosmosReviewStore(get_database())

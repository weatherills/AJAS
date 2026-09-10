"""Cosmos DB implementation of ReviewStore."""

from __future__ import annotations

from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.review.constants import AUDIT_CONTAINER, DECISIONS_CONTAINER, MATCHES_CONTAINER
from app.review.memory import InMemoryReviewStore
from app.review.models import AuditEvent, DecisionEvent, ReviewMatch


class CosmosReviewStore:
    def __init__(self, database: Any) -> None:
        self._matches = database.get_container_client(MATCHES_CONTAINER)
        self._decisions = database.get_container_client(DECISIONS_CONTAINER)
        self._audits = database.get_container_client(AUDIT_CONTAINER)

    def create_match(self, user_id: str, **kwargs: Any) -> ReviewMatch:
        working = self._hydrate()
        saved = working.create_match(user_id, **kwargs)
        self._persist_working(working)
        return saved

    def update_pending_match(self, user_id: str, match_id: str, **kwargs: Any) -> ReviewMatch:
        working = self._hydrate()
        saved = working.update_pending_match(user_id, match_id, **kwargs)
        self._persist_working(working)
        return saved

    def discard_pending_match(self, user_id: str, match_id: str) -> None:
        working = self._hydrate()
        working.discard_pending_match(user_id, match_id)
        try:
            self._matches.delete_item(item=match_id, partition_key=user_id)
        except (CosmosResourceNotFoundError, AttributeError, TypeError):
            pass
        self._persist_working(working)

    def get_match(self, match_id: str, *, user_id: str) -> ReviewMatch:
        return self._hydrate().get_match(match_id, user_id=user_id)

    def list_matches(self, user_id: str, **kwargs: Any) -> list[ReviewMatch]:
        return self._hydrate().list_matches(user_id, **kwargs)

    def claim_match(self, user_id: str, match_id: str, owner: str, **kwargs: Any) -> ReviewMatch:
        working = self._hydrate()
        saved = working.claim_match(user_id, match_id, owner, **kwargs)
        self._persist_working(working)
        return saved

    def release_lock(self, user_id: str, match_id: str, owner: str) -> ReviewMatch:
        working = self._hydrate()
        saved = working.release_lock(user_id, match_id, owner)
        self._persist_working(working)
        return saved

    def decide(self, user_id: str, match_id: str, decision: str, **kwargs: Any):
        working = self._hydrate()
        saved = working.decide(user_id, match_id, decision, **kwargs)
        self._persist_working(working)
        return saved

    def reopen(self, user_id: str, match_id: str) -> ReviewMatch:
        working = self._hydrate()
        saved = working.reopen(user_id, match_id)
        self._persist_working(working)
        return saved

    def list_decisions(self, user_id: str, match_id: str | None = None) -> list[DecisionEvent]:
        return self._hydrate().list_decisions(user_id, match_id)

    def record_audit(self, **kwargs: Any) -> AuditEvent:
        working = self._hydrate()
        saved = working.record_audit(**kwargs)
        self._persist_working(working)
        return saved

    def list_audit(self, user_id: str, **kwargs: Any) -> list[AuditEvent]:
        return self._hydrate().list_audit(user_id, **kwargs)

    def _all_items(self, client: Any) -> list[dict]:
        try:
            return list(client.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))
        except TypeError:
            return list(client.query_items(query="SELECT * FROM c"))

    def _hydrate(self) -> InMemoryReviewStore:
        working = InMemoryReviewStore()
        working._matches = {
            row.id: row for row in (ReviewMatch.model_validate(item) for item in self._all_items(self._matches))
        }
        working._decisions = {
            row.id: row
            for row in (DecisionEvent.model_validate(item) for item in self._all_items(self._decisions))
        }
        working._audits = {
            row.id: row for row in (AuditEvent.model_validate(item) for item in self._all_items(self._audits))
        }
        return working

    def _upsert(self, client: Any, payload: dict) -> None:
        try:
            client.replace_item(item=payload["id"], body=payload)
        except CosmosResourceNotFoundError:
            client.create_item(body=payload)

    def _persist_working(self, working: InMemoryReviewStore) -> None:
        for row in working._matches.values():
            self._upsert(self._matches, row.model_dump())
        for row in working._decisions.values():
            self._upsert(self._decisions, row.model_dump())
        for row in working._audits.values():
            self._upsert(self._audits, row.model_dump())

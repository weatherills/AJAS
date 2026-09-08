"""Review & Decision database layer (Cosmos schema + store).

Implements the Database PRD: matches with queue status and AI snapshots,
append-only decision_events (with supersedes_decision_id), and append-only
audit_events. The in-memory store is the rule engine; Cosmos hydrates and
persists the same documents. Saved vs AI is encoded as source on the match
row — there is no separate saved_queue container in this slice.
"""

from app.review.constants import (
    AUDIT_CONTAINER,
    DECISIONS_CONTAINER,
    MATCHES_CONTAINER,
    MAX_COMMENT_CHARS,
)
from app.review.containers import container_specs, ensure_review_containers
from app.review.errors import (
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewPreconditionError,
    ReviewStoreError,
    ReviewValidationError,
)
from app.review.memory import InMemoryReviewStore
from app.review.models import AuditEvent, DecisionEvent, ReviewMatch
from app.review.store import ReviewStore, get_review_store

__all__ = [
    "AUDIT_CONTAINER",
    "DECISIONS_CONTAINER",
    "MATCHES_CONTAINER",
    "MAX_COMMENT_CHARS",
    "AuditEvent",
    "DecisionEvent",
    "InMemoryReviewStore",
    "ReviewConflictError",
    "ReviewMatch",
    "ReviewNotFoundError",
    "ReviewPreconditionError",
    "ReviewStore",
    "ReviewStoreError",
    "ReviewValidationError",
    "container_specs",
    "ensure_review_containers",
    "get_review_store",
]

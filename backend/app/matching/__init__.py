"""Matching & Ranking database layer (Cosmos schema + store).

Implements the Database PRD: match_runs with keyword/semantic scores,
user_match_prefs + immutable history, model_registry, and optional
match_explanations. The in-memory store is the rule engine; Cosmos hydrates
and persists the same documents.
"""

from app.matching.constants import (
    DEFAULT_MODEL_ID,
    DEFAULT_THRESHOLD_PCT,
    RUNS_CONTAINER,
)
from app.matching.containers import container_specs, ensure_matching_containers
from app.matching.errors import (
    MatchingConflictError,
    MatchingNotFoundError,
    MatchingPayloadTooLargeError,
    MatchingRateLimitedError,
    MatchingStoreError,
    MatchingValidationError,
)
from app.matching.keys import idempotency_key, overall_score_pct
from app.matching.memory import InMemoryMatchingStore
from app.matching.models import MatchExplanation, MatchRun, ModelRegistry, UserMatchPrefs
from app.matching.store import MatchingStore, get_matching_store

__all__ = [
    "DEFAULT_MODEL_ID",
    "DEFAULT_THRESHOLD_PCT",
    "RUNS_CONTAINER",
    "InMemoryMatchingStore",
    "MatchExplanation",
    "MatchRun",
    "MatchingConflictError",
    "MatchingNotFoundError",
    "MatchingPayloadTooLargeError",
    "MatchingRateLimitedError",
    "MatchingStore",
    "MatchingStoreError",
    "MatchingValidationError",
    "ModelRegistry",
    "UserMatchPrefs",
    "container_specs",
    "ensure_matching_containers",
    "get_matching_store",
    "idempotency_key",
    "overall_score_pct",
]

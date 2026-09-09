"""Matching & Ranking database constants (Database PRD)."""

from typing import Final, Literal

RunStatus = Literal["queued", "running", "completed", "error"]
RunSource = Literal["sync", "async", "batch"]

RUN_STATUSES: Final[frozenset[str]] = frozenset({"queued", "running", "completed", "error"})
RUN_SOURCES: Final[frozenset[str]] = frozenset({"sync", "async", "batch"})

DEFAULT_THRESHOLD_PCT: Final[int] = 70
DEFAULT_SAVE_ALL: Final[bool] = False
DEFAULT_KEYWORD_WEIGHT: Final[float] = 0.4
DEFAULT_SEMANTIC_WEIGHT: Final[float] = 0.6
RETENTION_DAYS: Final[int] = 547  # 18 months

DEFAULT_MODEL_ID: Final[str] = "matching-v1"

RUNS_CONTAINER: Final[str] = "match_runs"
EXPLANATIONS_CONTAINER: Final[str] = "match_explanations"
PREFS_CONTAINER: Final[str] = "user_match_prefs"
HISTORY_CONTAINER: Final[str] = "user_match_pref_history"
MODELS_CONTAINER: Final[str] = "model_registry"

RUNS_PK: Final[str] = "/user_id"
EXPLANATIONS_PK: Final[str] = "/match_id"
PREFS_PK: Final[str] = "/user_id"
HISTORY_PK: Final[str] = "/user_id"
MODELS_PK: Final[str] = "/id"


def _policy(*composites: list[dict]) -> dict:
    return {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": "/\"_etag\"/?"}],
        "compositeIndexes": list(composites),
    }


RUNS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/job_id", "order": "ascending"},
    ],
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/resume_id", "order": "ascending"},
    ],
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/completed_at", "order": "descending"},
    ],
    [{"path": "/idempotency_key", "order": "ascending"}],
    [{"path": "/meets_threshold", "order": "ascending"}],
)
EXPLANATIONS_INDEXING: Final[dict] = _policy([{"path": "/match_id", "order": "ascending"}])
PREFS_INDEXING: Final[dict] = _policy([{"path": "/user_id", "order": "ascending"}])
HISTORY_INDEXING: Final[dict] = _policy(
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/created_at", "order": "descending"},
    ]
)
MODELS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/ai_service", "order": "ascending"},
        {"path": "/scorer_model", "order": "ascending"},
        {"path": "/scorer_model_version", "order": "ascending"},
        {"path": "/formula_version", "order": "ascending"},
    ]
)

"""Review & Decision database constants (Database PRD)."""

from typing import Final, Literal

MatchStatus = Literal["PENDING", "APPROVED", "REJECTED"]
MatchSource = Literal["ai", "saved"]
Suggestion = Literal["approve", "reject", "none", "review"]
DecisionValue = Literal["approve", "reject"]
DecisionSource = Literal["manual", "system"]

MATCH_STATUSES: Final[frozenset[str]] = frozenset({"PENDING", "APPROVED", "REJECTED"})
MATCH_SOURCES: Final[frozenset[str]] = frozenset({"ai", "saved"})
SUGGESTIONS: Final[frozenset[str]] = frozenset({"approve", "reject", "none", "review"})
DECISIONS: Final[frozenset[str]] = frozenset({"approve", "reject"})
DECISION_SOURCES: Final[frozenset[str]] = frozenset({"manual", "system"})

MAX_COMMENT_CHARS: Final[int] = 2000
DEFAULT_LOCK_SECONDS: Final[int] = 120
OVERWRITE_WINDOW_HOURS: Final[int] = 24
IDEMPOTENCY_TTL_HOURS: Final[int] = 24
DEFAULT_PAGE_SIZE: Final[int] = 25
MIN_PAGE_SIZE: Final[int] = 10
MAX_PAGE_SIZE: Final[int] = 100
SAS_TTL_MINUTES: Final[int] = 10
READ_SCOPE: Final[str] = "read:review"
WRITE_SCOPE: Final[str] = "write:review"
DECISION_QUEUE: Final[str] = "decision-events"
ENRICH_QUEUE: Final[str] = "review-enrich"
POISON_DEQUEUE: Final[int] = 5

MATCHES_CONTAINER: Final[str] = "matches"
DECISIONS_CONTAINER: Final[str] = "decision_events"
AUDIT_CONTAINER: Final[str] = "audit_events"

MATCHES_PK: Final[str] = "/user_id"
DECISIONS_PK: Final[str] = "/user_id"
AUDIT_PK: Final[str] = "/user_id"


def _policy(*composites: list[dict]) -> dict:
    return {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": "/\"_etag\"/?"}],
        "compositeIndexes": list(composites),
    }


MATCHES_INDEXING: Final[dict] = _policy(
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/status", "order": "ascending"},
        {"path": "/queued_at", "order": "descending"},
    ],
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/ai_score", "order": "descending"},
    ],
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/job_title", "order": "ascending"},
    ],
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/company", "order": "ascending"},
    ],
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/location", "order": "ascending"},
    ],
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/decided_at", "order": "descending"},
    ],
    [{"path": "/latest_decision_id", "order": "ascending"}],
)
DECISIONS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/match_id", "order": "ascending"},
        {"path": "/decided_at", "order": "descending"},
    ]
)
AUDIT_INDEXING: Final[dict] = _policy(
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/match_id", "order": "ascending"},
        {"path": "/occurred_at", "order": "descending"},
    ],
    [
        {"path": "/user_id", "order": "ascending"},
        {"path": "/event_type", "order": "ascending"},
        {"path": "/occurred_at", "order": "descending"},
    ],
)

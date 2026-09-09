"""Job Source Integration database constants (Database PRD)."""

from typing import Final, Literal

SourceType = Literal["greenhouse", "lever"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "partial_success"]
ListingState = Literal["open", "closed", "unknown"]

SOURCE_TYPES: Final[frozenset[str]] = frozenset({"greenhouse", "lever"})
RUN_STATUSES: Final[frozenset[str]] = frozenset(
    {"queued", "running", "succeeded", "failed", "partial_success"}
)
LISTING_STATES: Final[frozenset[str]] = frozenset({"open", "closed", "unknown"})

SEEDED_SOURCES: Final[tuple[tuple[str, str], ...]] = (
    ("greenhouse", "Greenhouse"),
    ("lever", "Lever"),
)

DEFAULT_TOKENS_PER_MIN: Final[int] = 60
DEFAULT_BURST: Final[int] = 10
DEFAULT_CRAWL_INTERVAL_SECONDS: Final[int] = 3600

SOURCES_CONTAINER: Final[str] = "job_sources"
TENANTS_CONTAINER: Final[str] = "source_tenants"
RUNS_CONTAINER: Final[str] = "source_fetch_runs"
REQUESTS_CONTAINER: Final[str] = "fetch_requests"
CURSORS_CONTAINER: Final[str] = "fetch_cursors"
RAW_CONTAINER: Final[str] = "job_postings_raw"
CANONICAL_CONTAINER: Final[str] = "job_postings_canonical"
LINKS_CONTAINER: Final[str] = "job_posting_links"
RATE_LIMITS_CONTAINER: Final[str] = "source_rate_limits"
SCHEDULES_CONTAINER: Final[str] = "crawl_schedules"

SOURCES_PK: Final[str] = "/id"
TENANTS_PK: Final[str] = "/source_id"
RUNS_PK: Final[str] = "/source_tenant_id"
REQUESTS_PK: Final[str] = "/source_tenant_id"
CURSORS_PK: Final[str] = "/source_tenant_id"
RAW_PK: Final[str] = "/source_tenant_id"
CANONICAL_PK: Final[str] = "/id"
LINKS_PK: Final[str] = "/raw_id"
RATE_LIMITS_PK: Final[str] = "/source_tenant_id"
SCHEDULES_PK: Final[str] = "/source_tenant_id"


def _policy(*composites: list[dict]) -> dict:
    return {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": "/\"_etag\"/?"}],
        "compositeIndexes": list(composites),
    }


SOURCES_INDEXING: Final[dict] = _policy([{"path": "/type", "order": "ascending"}])
TENANTS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/source_id", "order": "ascending"},
        {"path": "/tenant_key", "order": "ascending"},
    ]
)
RUNS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/source_tenant_id", "order": "ascending"},
        {"path": "/started_at", "order": "descending"},
    ]
)
REQUESTS_INDEXING: Final[dict] = _policy(
    [{"path": "/run_id", "order": "ascending"}],
    [
        {"path": "/source_tenant_id", "order": "ascending"},
        {"path": "/request_ts", "order": "ascending"},
    ],
    [{"path": "/status_code", "order": "ascending"}],
)
CURSORS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/source_tenant_id", "order": "ascending"},
        {"path": "/endpoint", "order": "ascending"},
    ]
)
RAW_INDEXING: Final[dict] = _policy(
    [
        {"path": "/source_tenant_id", "order": "ascending"},
        {"path": "/source_posting_id", "order": "ascending"},
    ],
    [{"path": "/dedupe_hash", "order": "ascending"}],
    [{"path": "/is_current", "order": "ascending"}],
    [{"path": "/seen_last_at", "order": "descending"}],
)
CANONICAL_INDEXING: Final[dict] = _policy(
    [{"path": "/canonical_key", "order": "ascending"}],
    [{"path": "/dedupe_hash", "order": "ascending"}],
    [{"path": "/is_active", "order": "ascending"}],
)
LINKS_INDEXING: Final[dict] = _policy(
    [{"path": "/canonical_id", "order": "ascending"}],
    [{"path": "/raw_id", "order": "ascending"}],
)
RATE_LIMITS_INDEXING: Final[dict] = _policy(
    [{"path": "/source_tenant_id", "order": "ascending"}],
    [{"path": "/backoff_until", "order": "ascending"}],
)
SCHEDULES_INDEXING: Final[dict] = _policy(
    [
        {"path": "/next_run_after", "order": "ascending"},
        {"path": "/is_paused", "order": "ascending"},
    ]
)

"""Job Source Integration database layer (Cosmos schema + store).

Implements the Database PRD: seeded Greenhouse/Lever sources, tenants, fetch
runs, cursors, token-bucket rate limits, crawl schedules, raw snapshots with a
single current row per posting, and canonical merge via job_posting_links.
"""

from app.job_sources.constants import (
    CANONICAL_CONTAINER,
    RAW_CONTAINER,
    SOURCES_CONTAINER,
    TENANTS_CONTAINER,
)
from app.job_sources.containers import container_specs, ensure_job_source_containers
from app.job_sources.errors import (
    JobSourceConflictError,
    JobSourceNotFoundError,
    JobSourceRateLimitedError,
    JobSourceStoreError,
    JobSourceValidationError,
)
from app.job_sources.keys import canonical_key, dedupe_hash, response_hash
from app.job_sources.memory import InMemoryJobSourceStore
from app.job_sources.models import (
    CrawlSchedule,
    FetchCursor,
    FetchRequest,
    JobPostingCanonical,
    JobPostingLink,
    JobPostingRaw,
    JobSource,
    SourceFetchRun,
    SourceRateLimit,
    SourceTenant,
)
from app.job_sources.store import JobSourceStore, get_job_source_store

__all__ = [
    "CANONICAL_CONTAINER",
    "RAW_CONTAINER",
    "SOURCES_CONTAINER",
    "TENANTS_CONTAINER",
    "CrawlSchedule",
    "FetchCursor",
    "FetchRequest",
    "InMemoryJobSourceStore",
    "JobPostingCanonical",
    "JobPostingLink",
    "JobPostingRaw",
    "JobSource",
    "JobSourceConflictError",
    "JobSourceNotFoundError",
    "JobSourceRateLimitedError",
    "JobSourceStore",
    "JobSourceStoreError",
    "JobSourceValidationError",
    "SourceFetchRun",
    "SourceRateLimit",
    "SourceTenant",
    "canonical_key",
    "container_specs",
    "dedupe_hash",
    "ensure_job_source_containers",
    "get_job_source_store",
    "response_hash",
]

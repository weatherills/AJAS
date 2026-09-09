"""Pydantic documents for Job Source Cosmos containers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.job_sources.constants import ListingState, RunStatus, SourceType


def new_id() -> str:
    return str(uuid4())


class JobSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    type: SourceType
    name: str
    created_at: str
    updated_at: str


class SourceTenant(BaseModel):
    """One org/board/subdomain. Unique (source_id, tenant_key)."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    source_id: str
    tenant_key: str
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: str
    updated_at: str


class SourceFetchRun(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    source_tenant_id: str
    status: RunStatus = "queued"
    started_at: str | None = None
    finished_at: str | None = None
    fetched_count: int = 0
    upsert_count: int = 0
    noop_count: int = 0
    error_count: int = 0
    error_summary: str | None = None
    expected_count: int = 0
    completed_count: int = 0
    created_at: str
    updated_at: str


class FetchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    source_tenant_id: str
    run_id: str
    endpoint: str
    url: str
    status_code: int | None = None
    retry_count: int = 0
    backoff_ms: int = 0
    rate_limited: bool = False
    error: str | None = None
    request_ts: str
    created_at: str


class FetchCursor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    source_tenant_id: str
    endpoint: str
    cursor: str | None = None
    updated_at: str


class JobPostingRaw(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    source_tenant_id: str
    source_posting_id: str
    title: str
    location: str = ""
    employment_type: str = ""
    company: str = ""
    apply_url: str = ""
    listing_state: ListingState = "open"
    body: str = ""
    content_blob_url: str | None = None
    response_hash: str
    canonical_key: str
    dedupe_hash: str
    is_current: bool = True
    seen_first_at: str
    seen_last_at: str
    created_at: str
    updated_at: str


class JobPostingCanonical(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    canonical_key: str
    dedupe_hash: str
    title: str
    location: str = ""
    employment_type: str = ""
    is_active: bool = True
    created_at: str
    updated_at: str


class JobPostingLink(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    raw_id: str
    canonical_id: str
    confidence: float = 1.0
    reason: str = "exact"
    created_at: str
    updated_at: str


class SourceRateLimit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    source_tenant_id: str
    effective_per_min: int
    burst: int
    tokens_remaining: float
    window_start: str
    backoff_until: str | None = None
    updated_at: str


class CrawlSchedule(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    source_tenant_id: str
    interval_seconds: int
    next_run_after: str
    is_paused: bool = False
    updated_at: str

"""Pydantic documents for Matching Cosmos containers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.matching.constants import RunSource, RunStatus


def new_id() -> str:
    return str(uuid4())


class ModelRegistry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    ai_service: str
    scorer_model: str
    scorer_model_version: str
    formula_version: str
    keyword_weight: float
    semantic_weight: float
    normalization_method: str
    prompt_version: str
    created_at: str
    updated_at: str


class UserMatchPrefs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    threshold_pct: int
    save_all_matches: bool = False
    version: int = 1
    created_at: str
    updated_at: str


class UserMatchPrefHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    threshold_pct: int
    save_all_matches: bool
    version: int
    created_at: str
    detail: dict[str, Any] = Field(default_factory=dict)


class MatchRun(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    resume_id: str | None = None
    resume_hash: str | None = None
    job_id: str | None = None
    job_hash: str | None = None
    model_version_id: str
    keyword_raw: float = 0.0
    keyword_norm: float = 0.0
    semantic_raw: float = 0.0
    semantic_norm: float = 0.0
    overall_score_pct: int = 0
    threshold_used: int
    meets_threshold: bool = False
    decision_saved: bool = False
    explanation_summary: str | None = None
    explanation_blob_uri: str | None = None
    feature_vector_blob_uri: str | None = None
    idempotency_key: str
    run_status: RunStatus = "completed"
    error_message: str | None = None
    source: RunSource = "sync"
    created_at: str
    completed_at: str | None = None
    updated_at: str


class MatchExplanation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    match_id: str
    summary: str
    highlights: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    explanation_blob_uri: str | None = None
    created_at: str
    updated_at: str

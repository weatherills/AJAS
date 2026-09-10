"""Pydantic documents for Learning Loop Cosmos containers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.learning.constants import (
    DecisionValue,
    ParamSource,
    ParamStatus,
    RecommendationStatus,
    TuningMode,
)
from app.learning.keys import new_id


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    job_id: str
    resume_id: str | None = None
    score: float
    score_components: dict[str, float] = Field(default_factory=dict)
    weight_config_id: str
    threshold: float
    recommended: bool = True
    status: RecommendationStatus = "pending"
    generated_at: str
    expires_at: str | None = None
    model_version: str


class DecisionLog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    recommendation_id: str
    job_id: str
    decision: DecisionValue
    comment_enc: str | None = None
    score_at_decision: float
    threshold_at_decision: float
    features_snapshot_ref: str | None = None
    model_version: str
    idempotency_key: str
    created_at: str
    updated_at: str


class WeightConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    weight_config_id: str
    weights: dict[str, float]
    threshold: float
    is_active: bool = False
    superseded_id: str | None = None
    created_at: str


class WeightTuningEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    tuning_event_id: str = ""
    user_id: str | None = None
    old_config_id: str
    new_config_id: str
    diff: dict[str, Any] = Field(default_factory=dict)
    reason: str
    automatic: bool = True
    rolled_back: bool = False
    created_at: str


class ModelParams(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    weights: dict[str, float]
    score_threshold: float
    model_version: str
    status: ParamStatus = "active"
    source: ParamSource = "global"
    tuning_mode: TuningMode = "auto"
    strictness: int = 1
    sample_size: int = 0
    effective_at: str
    updated_at: str
    previous: dict[str, Any] | None = None


class MetricsSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    scope_ref: str
    scope_type: str
    user_id: str | None = None
    period_start: str
    period_end: str
    weight_config_id: str | None = None
    recommendations: int = 0
    decisions: int = 0
    approvals: int = 0
    rejections: int = 0
    skips: int = 0
    suggestions_shown: int = 0
    scored_above_min: int = 0
    precision_proxy: float = 0.0
    recall_proxy: float = 0.0
    at_3: float = 0.0
    at_10: float = 0.0
    threshold: float = 0.7
    model_version: str
    notes: str | None = None

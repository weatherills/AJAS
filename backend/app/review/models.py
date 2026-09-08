"""Pydantic documents for Review Cosmos containers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.review.constants import DecisionSource, DecisionValue, MatchSource, MatchStatus, Suggestion


def new_id() -> str:
    return str(uuid4())


class ReviewMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    job_id: str
    resume_id: str | None = None
    status: MatchStatus = "PENDING"
    source: MatchSource = "ai"
    job_title: str = ""
    company: str = ""
    location: str = ""
    ai_score: float | None = None
    suggestion: Suggestion = "none"
    why: str | None = None
    summary: str | None = None
    summary_blob_uri: str | None = None
    highlights_json: list[Any] | None = None
    latest_decision_id: str | None = None
    queued_at: str
    decided_at: str | None = None
    lock_owner: str | None = None
    lock_expires_at: str | None = None
    etag: str = "1"
    created_at: str
    updated_at: str


class DecisionEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    match_id: str
    decision: DecisionValue
    comment: str | None = None
    source: DecisionSource = "manual"
    version: int = 1
    supersedes_decision_id: str | None = None
    ai_score: float | None = None
    suggestion: Suggestion | None = None
    idempotency_key: str | None = None
    decided_at: str
    created_at: str


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    match_id: str | None = None
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str

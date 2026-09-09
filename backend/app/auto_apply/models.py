"""Pydantic documents for Auto-Apply Cosmos containers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.auto_apply.constants import (
    AttemptStatus,
    AutofillSource,
    CoverSource,
    Mode,
    StatusEventType,
    SubmitStatus,
    Vendor,
)


def new_id() -> str:
    return str(uuid4())


class AutoApplyAttempt(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    job_id: str | None = None
    source_application_id: str | None = None
    posting_url: str | None = None
    vendor: Vendor
    mode: Mode = "api"
    status: AttemptStatus = "draft"
    approved: bool = False
    approved_ts: str | None = None
    resume_id: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_at: str
    updated_at: str


class ApplyPackage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    auto_apply_id: str
    user_id: str
    resume_variant_id: str | None = None
    cover_letter_id: str | None = None
    filled_fields_json: dict[str, Any] = Field(default_factory=dict)
    deep_link_url: str | None = None
    package_blob_uri: str | None = None
    locked: bool = False
    created_at: str
    updated_at: str


class ResumeVariant(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    resume_id: str | None = None
    label: str
    blob_uri: str
    created_at: str
    updated_at: str


class CoverLetter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    auto_apply_id: str | None = None
    source: CoverSource = "none"
    blob_uri: str | None = None
    body_text: str | None = None
    created_at: str
    updated_at: str


class FormAutofillValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    auto_apply_id: str
    user_id: str
    vendor: Vendor
    field_key: str
    value: str | None = None
    required: bool = False
    confidence: float | None = None
    source: AutofillSource = "resume"
    created_at: str
    updated_at: str


class VendorFieldMapping(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    vendor: Vendor
    normalized_key: str
    vendor_field_key: str
    required: bool = False
    transform: str | None = None
    created_at: str
    updated_at: str


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    auto_apply_id: str
    user_id: str
    vendor: Vendor
    status: SubmitStatus = "queued"
    idempotency_key: str
    vendor_request_id: str | None = None
    vendor_application_id: str | None = None
    request_blob_uri: str | None = None
    response_blob_uri: str | None = None
    retry_count: int = 0
    rate_limited_until: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class StatusEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    auto_apply_id: str
    user_id: str
    event_type: StatusEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_ts: str


class WebhookCallback(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    vendor: Vendor
    vendor_application_id: str
    auto_apply_id: str | None = None
    user_id: str | None = None
    dedupe_key: str
    event_type: str
    payload_blob_uri: str | None = None
    received_at: str
    expires_at: str

"""Pydantic documents for Resume Management Cosmos containers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.resumes.constants import ChildSource, ParseEventType, ProcessingStatus


def new_id() -> str:
    return str(uuid4())


class ResumeContact(BaseModel):
    """Optional 1:1 contact/profile row for a resume."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    resume_id: str
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    source: ChildSource = "parsed"
    parsing_confidence: int | None = None
    updated_at: str


class ResumeSkill(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    resume_id: str
    name: str
    order_index: int = 0
    source: ChildSource = "parsed"
    parsing_confidence: int | None = None
    updated_at: str


class ResumeExperience(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    resume_id: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    description: str | None = None
    order_index: int = 0
    source: ChildSource = "parsed"
    parsing_confidence: int | None = None
    updated_at: str


class ResumeEducation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    resume_id: str
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    notes: str | None = None
    order_index: int = 0
    source: ChildSource = "parsed"
    parsing_confidence: int | None = None
    updated_at: str


class StructuredResume(BaseModel):
    """Child snapshot written on parse success or manual edit."""

    model_config = ConfigDict(extra="ignore")

    contact: ResumeContact | None = None
    skills: list[ResumeSkill] = Field(default_factory=list)
    experiences: list[ResumeExperience] = Field(default_factory=list)
    educations: list[ResumeEducation] = Field(default_factory=list)


class Resume(BaseModel):
    """Parent resume document — Cosmos container ``resumes``, pk ``/user_id``."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    original_filename: str
    mime_type: str
    file_size: int
    blob_uri: str
    preview_blob_uri: str | None = None
    text_preview: str | None = None
    checksum_sha256: str
    processing_status: ProcessingStatus = "uploaded"
    parsed_at: str | None = None
    parsing_error: str | None = None
    is_deleted: bool = False
    deleted_at: str | None = None
    validated: bool = False
    validated_at: str | None = None
    last_edited_by: str | None = None
    created_at: str
    updated_at: str
    contact: ResumeContact | None = None
    skills: list[ResumeSkill] = Field(default_factory=list)
    experiences: list[ResumeExperience] = Field(default_factory=list)
    educations: list[ResumeEducation] = Field(default_factory=list)

    def children_ordered(self) -> StructuredResume:
        return StructuredResume(
            contact=self.contact,
            skills=sorted(self.skills, key=lambda s: s.order_index),
            experiences=sorted(self.experiences, key=lambda e: e.order_index),
            educations=sorted(self.educations, key=lambda e: e.order_index),
        )


class LibraryPreview(BaseModel):
    """URIs safe to return from the library/preview path."""

    resume_id: str
    text_preview: str | None
    preview_blob_uri: str | None
    blob_uri: str | None


class RunResumeSelection(BaseModel):
    """Exactly one active resume per run. Container pk ``/run_id``."""

    model_config = ConfigDict(extra="ignore")

    id: str
    run_id: str
    user_id: str
    resume_id: str
    created_at: str


class ResumeParseEvent(BaseModel):
    """Append-only parse/edit log. Container pk ``/resume_id``."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    resume_id: str
    user_id: str
    event_type: ParseEventType
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str

"""Core platform entities from the Database PRDs.

These six documents are the cross-feature records every other container
hangs off: User, JobPosting, Resume, Application, MailThread, EventLog.
Feature-specific Cosmos models (matches, fetch runs, …) live next to their
feature packages; this module is the shared vocabulary for provisioning,
seeders, and GDPR delete.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    return str(uuid4())


class User(BaseModel):
    """Account root. Partition ``/id``. One row per job seeker."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email: str | None = None
    display_name: str | None = None
    status: str = "active"
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class JobPosting(BaseModel):
    """Canonical job posting (Greenhouse/Lever deduped). Container ``job_postings_canonical``."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    canonical_key: str
    dedupe_hash: str
    title: str
    company: str = ""
    location: str = ""
    employment_type: str = ""
    apply_url: str = ""
    is_active: bool = True
    source: str = "greenhouse"
    status: str = "open"
    scraped_at: str | None = None
    created_at: str
    updated_at: str


class StoredResume(BaseModel):
    """Uploaded resume version. Container ``resumes``, partition ``/user_id``."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    original_filename: str
    mime_type: str
    file_size: int
    blob_uri: str
    checksum_sha256: str
    processing_status: str = "uploaded"
    candidate_id: str | None = None
    is_deleted: bool = False
    created_at: str
    updated_at: str


class Application(BaseModel):
    """Auto-apply attempt (the Application record). Container ``auto_apply_attempts``."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    job_id: str | None = None
    resume_id: str | None = None
    vendor: str
    status: str = "draft"
    approved: bool = False
    created_at: str
    updated_at: str


class MailThread(BaseModel):
    """Email conversation linked to a job or application. Container ``email_threads``."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    user_id: str
    graph_conversation_id: str
    subject: str
    job_posting_id: str | None = None
    application_id: str | None = None
    last_message_at: str
    created_at: str
    updated_at: str


class EventLog(BaseModel):
    """Append-only platform telemetry. Container ``event_log``, TTL 30 days."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str | None = None
    event_type: str
    entity_type: str | None = None
    entity_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str


CORE_ENTITIES: dict[str, dict[str, Any]] = {
    "User": {
        "container": "users",
        "model": User,
        "partition_key": "/id",
        "relationships": (
            "User 1—N StoredResume",
            "User 1—N Application",
            "User 1—N MailThread",
            "User 1—N EventLog",
            "User 1—N matches (Review)",
        ),
        "query_patterns": (
            "point read by user id",
            "list active users by created_at desc",
        ),
    },
    "JobPosting": {
        "container": "job_postings_canonical",
        "model": JobPosting,
        "partition_key": "/id",
        "relationships": (
            "JobPosting 1—N job_posting_links — job_postings_raw",
            "JobPosting 1—N Application (job_id)",
            "JobPosting 1—N matches (job_id)",
            "JobPosting 0—N MailThread (job_posting_id)",
        ),
        "query_patterns": (
            "lookup by canonical_key",
            "lookup by dedupe_hash",
            "list is_active = true",
        ),
    },
    "Resume": {
        "container": "resumes",
        "model": StoredResume,
        "partition_key": "/user_id",
        "relationships": (
            "StoredResume N—1 User",
            "StoredResume 1—N Application (resume_id)",
            "StoredResume 1—N resume_contacts / resume_skills / resume_experiences / resume_educations",
            "StoredResume 1—N resume_parse_events",
        ),
        "query_patterns": (
            "list by user_id, is_deleted, updated_at desc",
            "filter processing_status",
            "checksum_sha256 duplicate check per user",
        ),
    },
    "Application": {
        "container": "auto_apply_attempts",
        "model": Application,
        "partition_key": "/user_id",
        "relationships": (
            "Application N—1 User",
            "Application N—1 JobPosting",
            "Application N—1 StoredResume",
            "Application 1—N status_events / submit_requests",
        ),
        "query_patterns": (
            "list by user_id + status",
            "lookup vendor + source_application_id",
        ),
    },
    "MailThread": {
        "container": "email_threads",
        "model": MailThread,
        "partition_key": "/email_account_id",
        "relationships": (
            "MailThread N—1 email_accounts",
            "MailThread 0—1 JobPosting",
            "MailThread 0—1 Application",
            "MailThread 1—N email_messages",
        ),
        "query_patterns": (
            "list by email_account_id, last_message_at desc",
            "lookup graph_conversation_id",
            "filter job_posting_id / application_id",
        ),
    },
    "EventLog": {
        "container": "event_log",
        "model": EventLog,
        "partition_key": "/user_id",
        "relationships": (
            "EventLog N—1 User (nullable for system events)",
            "EventLog references entity_type + entity_id",
        ),
        "query_patterns": (
            "list by user_id, occurred_at desc",
            "filter event_type",
            "GDPR delete audit by entity_type = user",
        ),
    },
}

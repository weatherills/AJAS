"""Central validators for DAO writes. Rejects incomplete Cosmos items."""

from __future__ import annotations

from typing import Any

from app.job_sources.constants import SOURCE_TYPES
from app.review.constants import DECISIONS, MATCH_STATUSES

REQUIRED: dict[str, tuple[str, ...]] = {
    "resumes": ("id", "user_id", "original_filename", "mime_type", "blob_uri"),
    "resume_versions": ("id", "resume_id", "user_id", "blob_uri"),
    "resume_contacts": ("id", "resume_id"),
    "resume_skills": ("id", "resume_id", "name"),
    "resume_experiences": ("id", "resume_id"),
    "resume_educations": ("id", "resume_id"),
    "job_postings_canonical": ("id", "canonical_key", "title", "source"),
    "job_postings_raw": ("id", "source_tenant_id", "source_posting_id"),
    "matches": ("id", "user_id", "job_id", "resume_id", "status"),
    "match_records": ("id", "userId", "jobId", "resumeId"),
    "email_threads": ("id", "email_account_id", "user_id"),
    "email_messages": ("id", "email_account_id", "email_thread_id"),
    "email_attachments": ("id", "email_account_id", "message_id", "filename"),
    "apply_runs": ("id", "userId"),
    "auto_apply_attempts": ("id", "user_id"),
    "cover_letters": ("id", "user_id"),
    "vendor_field_mappings": ("id", "vendor", "field"),
    "user_settings": ("id", "user_id"),
    "source_toggles": ("id", "userId"),
    "decision_log": ("id", "user_id", "decision"),
    "privacy_requests": ("id", "userId", "kind"),
    "decision_events": ("id", "user_id", "match_id", "decision"),
}


class SchemaValidationError(ValueError):
    """Item failed the container schema before a Cosmos write."""

    def __init__(self, container: str, message: str) -> None:
        super().__init__(f"{container}: {message}")
        self.container = container
        self.status_code = 400


def validate_item(container: str, row: dict[str, Any]) -> dict[str, Any]:
    required = REQUIRED.get(container, ("id",))
    missing = [field for field in required if not row.get(field) and row.get(field) != 0]
    if missing:
        raise SchemaValidationError(container, f"missing {missing}")
    if container == "job_postings_canonical":
        source = str(row.get("source") or "")
        if source not in SOURCE_TYPES:
            raise SchemaValidationError(container, "source must be greenhouse|lever")
    if container == "matches":
        status = str(row.get("status") or "")
        if status not in MATCH_STATUSES:
            raise SchemaValidationError(container, "status must be PENDING|APPROVED|REJECTED")
    if container in {"decision_log", "decision_events"}:
        decision = str(row.get("decision") or "")
        allowed = DECISIONS | {"skip"} if container == "decision_log" else DECISIONS
        if decision not in allowed:
            raise SchemaValidationError(container, f"decision must be one of {sorted(allowed)}")
    if container == "privacy_requests" and str(row.get("kind") or "") not in {"export", "delete", "redact"}:
        raise SchemaValidationError(container, "kind must be export|delete|redact")
    return row

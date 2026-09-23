"""Database Bootstrap epic: Kanban names mapped onto Database PRD containers.

The eight Database PRDs already name the physical Cosmos containers
(`decision_events`, `auto_apply_attempts`, …). The bootstrap Kanban uses
shorter aliases (`decisions`, `applications`, …). This module is the
single mapping, plus settings defaults and learning snapshot shape.
"""

from __future__ import annotations

from typing import Any

from app.settings.constants import DEFAULT_MATCH_THRESHOLD
from app.storage.catalog import container_by_id, container_catalog

# Kanban title → physical Database PRD container.
KANBAN_CONTAINERS: dict[str, str] = {
    "decisions": "decision_events",
    "reviews_history": "audit_events",
    "applications": "auto_apply_attempts",
    "application_events": "status_events",
    "user_settings": "user_settings",
    "source_toggles": "source_toggles",
    "resumes": "resumes",
    "resume_versions": "resume_versions",
    "resume_files": "resume_versions",
    "resume_parsed": "resume_parse_events",
    "job_postings": "job_postings_canonical",
    "job_posting_details": "job_postings_raw",
    "ingestion_jobs": "source_fetch_runs",
    "rate_limit_state": "source_rate_limits",
    "crawls": "source_fetch_runs",
    "matches": "matches",
    "match_records": "match_records",
    "match_evidence": "match_evidence",
    "scoring_runs": "scoring_runs",
    "review_queue": "matches",
    "review_decisions": "decision_events",
    "email_threads": "email_threads",
    "email_messages": "email_messages",
    "email_attachments": "email_attachments",
    "learning_events": "decision_log",
    "decision_feedback": "decision_log",
    "model_weight_overrides": "weight_config",
    "metrics_snapshots": "metrics_snapshot",
    "apply_runs": "apply_runs",
    "apply_attempts": "auto_apply_attempts",
    "form_field_mappings": "vendor_field_mappings",
    "cover_letters": "cover_letters",
    "data_subjects": "data_subjects",
    "privacy_requests": "privacy_requests",
    "export_bundles": "export_bundles",
    "retention_policies": "retention_policies",
    "retention_jobs": "retention_jobs",
    "legal_holds": "legal_holds",
    "pii_field_catalog": "pii_field_catalog",
    "privacy_audit_log": "privacy_audit_log",
    "candidates": "candidates",
    "companies": "companies",
    "recruiters": "recruiters",
    "recruiter_inboxes": "recruiter_inboxes",
    "resume_parse_queue": "resume_parse_queue",
    "resume_parsing_queue": "resume_parse_queue",
    "auto_apply_rules": "auto_apply_rules",
    "webhooks_outbox": "integration_outbox",
    "integration_outbox": "integration_outbox",
    "audit_logs": "event_log",
    "attachments": "attachments",
    "application_status_history": "status_events",
    "mail_threads": "email_threads",
    "mail_messages": "email_messages",
    "thread_participants": "email_recipients",
    "auto_apply_runs": "apply_runs",
    "auto_apply_run_items": "auto_apply_attempts",
    "matching_models": "model_registry",
    "scrape_jobs_queue": "scrape_jobs_queue",
    "rate_limits": "source_rate_limits",
    "oauth_credentials": "oauth_credentials",
    "webhooks_outbound": "webhooks_outbound",
    "webhook_deliveries": "webhook_deliveries",
}

SETTINGS_DEFAULTS: dict[str, Any] = {
    "matchThreshold": DEFAULT_MATCH_THRESHOLD,
    "sourceToggles": {"greenhouse": True, "lever": True, "autoApply": False},
    "emailConnection": {"provider": "microsoft_365", "status": "pending"},
    "theme": "system",
}

LEARNING_EVENT_SCHEMA: dict[str, str] = {
    "id": "string",
    "user_id": "string (PK)",
    "recommendation_id": "string",
    "decision": "approve | reject | skip",
    "decided_at": "iso-8601",
    "match_id": "string",
    "score": "float 0-1",
}

METRICS_SNAPSHOT_SCHEMA: dict[str, str] = {
    "id": "string",
    "scope_ref": "string (PK)",
    "scope_type": "user | global",
    "precision": "float",
    "recall": "float",
    "sample_count": "int",
    "window_end": "iso-8601",
    "weight_config_id": "string",
}

VERSION_TTL_SECONDS = 90 * 86_400


def resolve_container(kanban_name: str) -> str:
    try:
        return KANBAN_CONTAINERS[kanban_name]
    except KeyError as exc:
        raise KeyError(f"unknown bootstrap container {kanban_name!r}") from exc


def physical_containers() -> dict[str, str]:
    return dict(KANBAN_CONTAINERS)


def settings_document(user_id: str, **overrides: Any) -> dict[str, Any]:
    body = {
        "id": user_id,
        "user_id": user_id,
        "userId": user_id,
        "schemaVersion": 1,
        "match_threshold": SETTINGS_DEFAULTS["matchThreshold"],
        "matchThreshold": SETTINGS_DEFAULTS["matchThreshold"],
        "timezone": "UTC",
        "quietHoursStart": None,
        "quietHoursEnd": None,
        "greenhouse_enabled": SETTINGS_DEFAULTS["sourceToggles"]["greenhouse"],
        "lever_enabled": SETTINGS_DEFAULTS["sourceToggles"]["lever"],
        "auto_apply_enabled": SETTINGS_DEFAULTS["sourceToggles"]["autoApply"],
        "theme": SETTINGS_DEFAULTS["theme"],
        "email_connection": dict(SETTINGS_DEFAULTS["emailConnection"]),
    }
    body.update(overrides)
    return body


def persist_saved(*, score: float, threshold: int = DEFAULT_MATCH_THRESHOLD) -> bool:
    """True when a match should be stored as saved (score is 0-1, threshold is 0-100)."""
    return score * 100 >= float(threshold)


def composite_paths(container: str) -> list[list[str]]:
    policy = container_by_id(container).indexing_policy
    composites = policy.get("compositeIndexes") or []
    return [[part["path"] for part in index] for index in composites]


def unique_key_paths(container: str) -> list[tuple[str, ...]]:
    spec = container_by_id(container)
    return list(spec.unique_keys or ())


def catalog_covers_epic() -> list[str]:
    ids = {spec.id for spec in container_catalog()}
    missing = [name for name in KANBAN_CONTAINERS.values() if name not in ids]
    return missing

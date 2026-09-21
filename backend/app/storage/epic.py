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
    "resumes": "resumes",
    "resume_versions": "resume_versions",
    "job_postings": "job_postings_canonical",
    "crawls": "source_fetch_runs",
    "matches": "matches",
    "email_threads": "email_threads",
    "email_messages": "email_messages",
    "learning_events": "decision_log",
    "metrics_snapshots": "metrics_snapshot",
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
        "schemaVersion": 1,
        "match_threshold": SETTINGS_DEFAULTS["matchThreshold"],
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

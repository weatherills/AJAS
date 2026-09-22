"""API / DAL / ownership / SLA overlay used by cosmos.schema.md."""

from __future__ import annotations

from typing import Any

from app.storage.consistency import container_consistency
from app.storage.pii import pii_paths
from app.storage.retention import RETENTION_DAYS

FEATURE_OWNER = {
    "platform": "platform",
    "review": "review",
    "matching": "matching",
    "settings": "settings",
    "resumes": "resumes",
    "job_sources": "ingest",
    "mail": "mail",
    "learning": "learning",
    "auto_apply": "apply",
    "privacy": "privacy",
}

FEATURE_API: dict[str, tuple[str, ...]] = {
    "review": ("GET /api/v1/matches", "POST /api/v1/matches/{matchId}/decision"),
    "matching": (
        "POST /api/v1/matches/rank",
        "GET /api/v1/match-records",
        "POST /api/v1/matching/prune",
        "POST /api/v1/matching/batch-rescore",
    ),
    "auto_apply": ("GET /api/v1/auto-apply/requests", "POST /api/v1/auto-apply/requests"),
    "mail": ("GET /api/v1/email/threads", "POST /api/v1/threads/{threadId}/reply"),
    "resumes": ("GET /api/resumes",),
    "job_sources": ("GET /api/v1/jobs",),
    "settings": ("GET /api/v1/settings",),
    "learning": ("GET /api/v1/metrics",),
    "platform": ("GET /api/v1/ops/storage",),
    "privacy": ("GET /api/v1/privacy/requests",),
}

CONTAINER_RETENTION_KEY = {
    "job_postings_canonical": "jobs",
    "job_postings_raw": "jobs",
    "email_messages": "emails",
    "email_threads": "emails",
    "event_log": "logs",
    "matches": "matches",
    "match_runs": "match_runs",
    "match_records": "matches",
    "match_evidence": "matches",
    "resumes": "resumes",
    "auto_apply_attempts": "applications",
    "webhook_callbacks": "webhooks",
    "status_events": "applications",
    "resume_versions": "resumes",
    "decision_events": "matches",
    "audit_events": "matches",
}

SLA = "p95 in-partition < 250ms; queue page of 25 ≤ 5 RU"


def ops_row(spec: Any) -> dict[str, Any]:
    key = CONTAINER_RETENTION_KEY.get(spec.id)
    retention = RETENTION_DAYS[key] if key else (spec.default_ttl // 86_400 if spec.default_ttl else None)
    return {
        "id": spec.id,
        "owner": FEATURE_OWNER.get(spec.feature, spec.feature),
        "consistency": container_consistency(spec.id),
        "api": FEATURE_API.get(spec.feature, ()),
        "retentionDays": retention,
        "pii": pii_paths(spec.id),
        "sla": SLA,
        "dal": f"CatalogRepository({spec.id})",
    }

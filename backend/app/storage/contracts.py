"""HTTP + queue + blob contract used by frontend live clients."""

from __future__ import annotations

from typing import Any

ENDPOINTS: tuple[dict[str, str], ...] = (
    {"id": "health", "method": "GET", "path": "/api/health", "client": "n/a"},
    {"id": "review.list", "method": "GET", "path": "/api/v1/matches", "client": "reviewLive.list"},
    {"id": "review.get", "method": "GET", "path": "/api/v1/matches/{matchId}", "client": "reviewLive.get"},
    {"id": "review.decide", "method": "POST", "path": "/api/v1/matches/{matchId}/decision", "client": "reviewLive.decide"},
    {"id": "review.reopen", "method": "POST", "path": "/api/v1/matches/{matchId}/reopen", "client": "reviewLive.reopen"},
    {"id": "review.bulk", "method": "POST", "path": "/api/v1/matches/bulk", "client": "reviewLive.bulk"},
    {"id": "review.history", "method": "GET", "path": "/api/v1/decisions/history", "client": "reviewLive.list"},
    {"id": "matching.rank", "method": "POST", "path": "/api/v1/matches/rank", "client": "matchingLive.scoreMany"},
    {"id": "matching.ops", "method": "GET", "path": "/api/v1/operations/{operationId}", "client": "matchingLive.scoreMany"},
    {"id": "autoApply.create", "method": "POST", "path": "/api/v1/auto-apply/requests", "client": "autoApplyLive.create"},
    {"id": "autoApply.list", "method": "GET", "path": "/api/v1/auto-apply/requests", "client": "autoApplyLive.list"},
    {"id": "autoApply.get", "method": "GET", "path": "/api/v1/auto-apply/requests/{request_id}", "client": "autoApplyLive.get"},
    {"id": "autoApply.cancel", "method": "POST", "path": "/api/v1/auto-apply/requests/{request_id}/cancel", "client": "autoApplyLive.cancel"},
    {"id": "email.status", "method": "GET", "path": "/api/v1/email/status", "client": "emailLive.status"},
    {"id": "email.threads", "method": "GET", "path": "/api/v1/email/threads", "client": "emailLive.listThreads"},
    {"id": "email.reply", "method": "POST", "path": "/api/v1/threads/{threadId}/reply", "client": "emailLive.reply"},
    {"id": "jobs.list", "method": "GET", "path": "/api/v1/jobs", "client": "jobsLive"},
    {"id": "resumes.list", "method": "GET", "path": "/api/resumes", "client": "resumeLive"},
    {"id": "settings.get", "method": "GET", "path": "/api/v1/settings", "client": "settingsLive"},
    {"id": "learning.metrics", "method": "GET", "path": "/api/v1/metrics", "client": "learningLive"},
    {"id": "ops.storage", "method": "GET", "path": "/api/v1/ops/storage", "client": "n/a"},
    {"id": "ops.queues", "method": "GET", "path": "/api/v1/ops/queues", "client": "n/a"},
    {"id": "ops.slo", "method": "GET", "path": "/api/v1/ops/slo", "client": "n/a"},
)


def endpoint_table() -> list[dict[str, str]]:
    return [dict(row) for row in ENDPOINTS]


def frontend_path_needles() -> list[str]:
    needles = []
    for row in ENDPOINTS:
        path = row["path"]
        if row["client"] == "n/a":
            continue
        needles.append(path.split("?")[0])
    return needles


# Frontend ReviewMatch (camelCase) ← Cosmos `matches` document (snake_case).
FE_DB_REVIEW_MATCH: dict[str, str] = {
    "matchId": "id",
    "jobId": "job_id",
    "resumeId": "resume_id",
    "jobTitle": "job_title",
    "company": "company",
    "location": "location",
    "score": "ai_score",
    "suggestion": "suggestion",
    "status": "status",
    "source": "source",
    "createdAt": "created_at",
    "updatedAt": "updated_at",
    "queuedAt": "queued_at",
    "etag": "etag",
    "why": "why",
    "summary": "summary",
    "latestDecisionId": "latest_decision_id",
    "decidedAt": "decided_at",
}

FE_DB_DECISION: dict[str, str] = {
    "decisionId": "id",
    "matchId": "match_id",
    "decision": "decision",
    "comment": "comment",
    "createdAt": "created_at",
    "aiScore": "ai_score",
    "suggestion": "suggestion",
}


def project_review_match(row: dict[str, Any]) -> dict[str, Any]:
    """Shape a Cosmos matches document as the frontend ReviewMatch DTO."""
    status = str(row.get("status") or "pending").lower()
    if status == "pending":
        status = "pending"
    return {
        "matchId": row.get("id"),
        "jobId": row.get("job_id"),
        "resumeId": row.get("resume_id"),
        "jobTitle": row.get("job_title"),
        "company": row.get("company"),
        "location": row.get("location"),
        "score": row.get("ai_score"),
        "suggestion": row.get("suggestion") or "none",
        "status": status if status in {"pending", "approved", "rejected"} else "pending",
        "source": row.get("source") or "ai",
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
        "queuedAt": row.get("queued_at"),
        "etag": row.get("etag") or row.get("_etag"),
        "why": row.get("why"),
        "summary": row.get("summary"),
        "latestDecisionId": row.get("latest_decision_id"),
        "decidedAt": row.get("decided_at"),
    }

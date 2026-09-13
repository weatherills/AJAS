"""GDPR export bundle and right-to-be-forgotten purge planner."""

from __future__ import annotations

from typing import Any

from app.matching.keys import utc_now


def export_bundle(
    *,
    user_id: str,
    jobs: list[dict[str, Any]] | None = None,
    emails: list[dict[str, Any]] | None = None,
    matches: list[dict[str, Any]] | None = None,
    resumes: list[dict[str, Any]] | None = None,
    logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "userId": user_id,
        "exportedAt": utc_now(),
        "jobs": jobs or [],
        "emails": emails or [],
        "matches": matches or [],
        "resumes": resumes or [],
        "logs": logs or [],
        "format": "ajas.gdpr.v1",
    }


def purge_plan(*, user_id: str, jobs: list[dict[str, Any]], emails: list[dict[str, Any]], matches: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "userId": user_id,
        "jobs": [item.get("id") for item in jobs if item.get("user_id") == user_id or not item.get("user_id")],
        "emails": [item.get("id") for item in emails if item.get("user_id") == user_id or not item.get("user_id")],
        "matches": [item.get("id") for item in matches if item.get("user_id") == user_id or not item.get("user_id")],
        "status": "planned",
    }


def apply_purge(plan: dict[str, Any]) -> dict[str, Any]:
    deleted = sum(len(plan.get(key) or []) for key in ("jobs", "emails", "matches"))
    return {"status": "purged", "deleted": deleted, "userId": plan.get("userId")}

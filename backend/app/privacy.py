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


def purge_plan(*, user_id: str, jobs: list[dict[str, Any]], emails: list[dict[str, Any]], matches: list[dict[str, Any]], resumes: list[dict[str, Any]] | None = None, applications: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    def _ids(rows: list[dict[str, Any]] | None) -> list[Any]:
        return [item.get("id") for item in rows or [] if item.get("user_id") == user_id or not item.get("user_id")]

    return {
        "userId": user_id,
        "jobs": _ids(jobs),
        "emails": _ids(emails),
        "matches": _ids(matches),
        "resumes": _ids(resumes),
        "applications": _ids(applications),
        "status": "planned",
    }


def apply_purge(plan: dict[str, Any], store: Any | None = None) -> dict[str, Any]:
    deleted = sum(len(plan.get(key) or []) for key in ("jobs", "emails", "matches", "resumes", "applications"))
    user_id = plan.get("userId")
    result: dict[str, Any] = {"status": "purged", "deleted": deleted, "userId": user_id}
    if user_id:
        try:
            from app.learning.runtime import get_service as get_learning
            from app.learning.runtime import try_get_service

            learning = try_get_service() or get_learning()
            learning.delete_user_data(str(user_id))
        except Exception:
            pass
    if store is not None and user_id:
        from app.storage.retention import execute_gdpr_delete

        gdpr = execute_gdpr_delete(store, str(user_id))
        result["deleted"] = deleted + int(gdpr.get("deletedDocs") or 0)
        result["gdpr"] = gdpr
    return result

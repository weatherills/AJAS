"""Recruiter portal views and expiring share tokens for jobs/matches."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.sprint12.billing import feature_allowed
from app.sprint12.tenants import can

_LINKS: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _LINKS.clear()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_link(
    *,
    tenant_id: str,
    actor_id: str,
    target_type: str,
    target_id: str,
    ttl_hours: int = 72,
) -> dict[str, Any]:
    if target_type not in {"job", "match"}:
        raise ValueError("target_type must be job or match")
    if not can(tenant_id, actor_id, "review.write"):
        raise PermissionError("cannot share")
    if not feature_allowed(tenant_id, "share_links"):
        raise PermissionError("plan does not include shareable links")
    token = hashlib.sha256(f"{tenant_id}:{target_id}:{uuid4()}".encode()).hexdigest()[:32]
    expires = _now() + timedelta(hours=int(ttl_hours))
    row = {
        "token": token,
        "tenantId": tenant_id,
        "targetType": target_type,
        "targetId": target_id,
        "createdBy": actor_id,
        "expiresAt": expires.isoformat(),
        "revoked": False,
    }
    _LINKS[token] = row
    return row


def resolve(token: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    row = _LINKS.get(token)
    if row is None or row.get("revoked"):
        return None
    expires = datetime.fromisoformat(row["expiresAt"])
    clock = now or _now()
    if clock >= expires:
        return None
    return row


def recruiter_view(token: str, *, job: dict[str, Any] | None = None, match: dict[str, Any] | None = None) -> dict[str, Any]:
    row = resolve(token)
    if row is None:
        raise KeyError("expired or unknown share link")
    tenant_id = row["tenantId"]
    if row["targetType"] == "match" and not feature_allowed(tenant_id, "recruiter_portal"):
        raise PermissionError("plan does not include recruiter portal")
    payload: dict[str, Any] = {
        "targetType": row["targetType"],
        "targetId": row["targetId"],
        "limited": True,
    }
    if job:
        payload["job"] = {
            "title": job.get("title"),
            "company": job.get("company"),
            "location": job.get("location"),
            "url": job.get("url"),
        }
    if match:
        payload["match"] = {
            "score": match.get("score"),
            "summary": match.get("summary"),
            "resumeHighlights": match.get("highlights") or [],
        }
    return payload


def revoke(token: str, *, actor_id: str) -> bool:
    row = _LINKS.get(token)
    if not row or row["createdBy"] != actor_id:
        return False
    row["revoked"] = True
    return True

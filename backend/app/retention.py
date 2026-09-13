"""Purge stale jobs and emails on a retention schedule."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings
from app.flags import feature_enabled
from app.job_sources.keys import parse_ts
from app.mail.pii import redact_pii

DAYS = {
    "jobs": 365,
    "emails": 180,
    "logs": 30,
    "matches": 365,
    "resumes": 730,
    "consent": 730,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def retention_days(artifact: str) -> int:
    return DAYS.get(artifact, 365)


def policy() -> dict[str, Any]:
    return {"schema": "ajas.retention.v1", "days": dict(DAYS)}


def expired(artifact: str, created_at: str, *, now: datetime | None = None) -> bool:
    return is_stale(created_at, days=retention_days(artifact), now=now)


def is_stale(stamp: str | None, *, days: int, now: datetime | None = None) -> bool:
    if not stamp or days <= 0:
        return False
    try:
        parsed = parse_ts(stamp)
    except Exception:
        return False
    cutoff = (now or _now()) - timedelta(days=days)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed < cutoff


def plan_purge(
    *,
    jobs: list[dict[str, Any]],
    emails: list[dict[str, Any]],
    job_days: int | None = None,
    mail_days: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    job_keep = job_days if job_days is not None else settings.job_retention_days
    mail_keep = mail_days if mail_days is not None else settings.mail_retention_days
    stale_jobs = [
        item.get("id")
        for item in jobs
        if is_stale(item.get("seen_last_at") or item.get("updated_at") or item.get("created_at"), days=job_keep, now=now)
    ]
    stale_mail = [
        item.get("id")
        for item in emails
        if is_stale(item.get("received_at") or item.get("created_at"), days=mail_keep, now=now)
    ]
    return {
        "enabled": feature_enabled("data_retention_purge"),
        "jobIds": [job_id for job_id in stale_jobs if job_id],
        "emailIds": [mail_id for mail_id in stale_mail if mail_id],
        "jobRetentionDays": job_keep,
        "mailRetentionDays": mail_keep,
        "policy": policy(),
    }


def apply_purge(store: Any | None, plan: dict[str, Any]) -> dict[str, Any]:
    if not plan.get("enabled"):
        return {"purgedJobs": 0, "purgedEmails": 0, "skipped": True}
    purged_jobs = 0
    purged_mail = 0
    if store is not None and hasattr(store, "deactivate_jobs"):
        purged_jobs = int(store.deactivate_jobs(plan.get("jobIds") or []))
    if store is not None and hasattr(store, "delete_messages"):
        purged_mail = int(store.delete_messages(plan.get("emailIds") or []))
    return {
        "purgedJobs": purged_jobs,
        "purgedEmails": purged_mail,
        "skipped": False,
        "note": redact_pii("retention purge applied"),
    }

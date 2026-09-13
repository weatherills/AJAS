"""Consent log for automated applies. Bulk apply still requires per-job consent."""

from __future__ import annotations

from typing import Any

from app.matching.keys import utc_now

_LOG: list[dict[str, Any]] = []


def reset() -> None:
    _LOG.clear()


def record(*, user_id: str, job_id: str, resume_id: str | None, approved: bool, source: str = "ui") -> dict[str, Any]:
    if not approved:
        raise ValueError("automated apply requires explicit consent")
    row = {
        "userId": user_id,
        "jobId": job_id,
        "resumeId": resume_id,
        "approved": True,
        "source": source,
        "at": utc_now(),
        "bulk": False,
    }
    _LOG.append(row)
    return row


def listing(*, user_id: str | None = None) -> list[dict[str, Any]]:
    rows = list(_LOG)
    if user_id:
        rows = [row for row in rows if row["userId"] == user_id]
    return rows

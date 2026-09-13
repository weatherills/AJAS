"""ZipRecruiter fixture adapter with cursor pagination and Retry-After backoff.

Live ZipRecruiter HTML scraping is out of the Job Source PRD. Flags default off.
"""

from __future__ import annotations

from typing import Any

from app.job_sources.boards import backoff_seconds, load_fixture_jobs
from app.job_sources.http_policy import jittered_backoff


def retry_after_seconds(payload: Any, attempt: int) -> float:
    """Honor fixture Retry-After when present, else exponential backoff with jitter."""
    retry_after = 0.0
    if isinstance(payload, dict):
        raw = payload.get("retry_after") or payload.get("retryAfter")
        try:
            retry_after = float(raw)
        except (TypeError, ValueError):
            retry_after = 0.0
    base = max(retry_after, backoff_seconds(attempt))
    return jittered_backoff(attempt, base=max(base, 0.25), jitter=0.0)


def paginate(payload: Any) -> list[dict[str, Any]]:
    """Walk cursor pages (`pages[].cursor` / `next`) falling back to a flat jobs list."""
    if isinstance(payload, dict) and isinstance(payload.get("pages"), list):
        out: list[dict[str, Any]] = []
        expected: str | None = None
        for index, page in enumerate(payload["pages"], start=1):
            if not isinstance(page, dict):
                continue
            cursor = str(page.get("cursor") or "")
            if expected is not None and cursor and cursor != expected:
                break
            jobs = page.get("jobs") if isinstance(page.get("jobs"), list) else []
            for job in jobs:
                if isinstance(job, dict):
                    out.append({**job, "page": int(job.get("page") or index), "cursor": cursor})
            nxt = page.get("next")
            expected = str(nxt) if nxt else None
            if not nxt:
                break
        return out
    if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        return [job for job in payload["jobs"] if isinstance(job, dict)]
    return []


def ziprecruiter_jobs(payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    jobs = paginate(payload)
    wrapped = {"jobs": jobs}
    rows = load_fixture_jobs("ziprecruiter", wrapped, listing_url=listing_url)
    _ = retry_after_seconds(payload, 0)
    return rows

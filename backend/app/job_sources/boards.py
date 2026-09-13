"""Optional Indeed/LinkedIn adapters.

Live HTML scraping is out of the Job Source PRD (Greenhouse/Lever only) and is
not implemented. These adapters ingest operator-supplied JSON fixtures when the
feature flag is on and robots/consent checks pass.
"""

from __future__ import annotations

from typing import Any

from app.flags import feature_enabled
from app.job_sources.robots import can_fetch

ALLOWED_FIXTURE_HOSTS = frozenset({"fixtures.ajas.local", "localhost", "127.0.0.1"})


def _normalize_row(source: str, job: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": source,
        "source_posting_id": str(job.get("id") or job.get("source_posting_id") or ""),
        "title": str(job.get("title") or ""),
        "company": str(job.get("company") or ""),
        "location": str(job.get("location") or ""),
        "employment_type": str(job.get("employment_type") or job.get("type") or ""),
        "body": str(job.get("description") or job.get("body") or ""),
        "apply_url": str(job.get("apply_url") or job.get("url") or ""),
    }


def load_fixture_jobs(source: str, payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    flag = "indeed_adapter" if source == "indeed" else "linkedin_adapter"
    if not feature_enabled(flag):
        return []
    if listing_url and not can_fetch(listing_url):
        return []
    rows = payload if isinstance(payload, list) else (payload.get("jobs") if isinstance(payload, dict) else [])
    if not isinstance(rows, list):
        return []
    out = []
    for job in rows:
        if not isinstance(job, dict):
            continue
        row = _normalize_row(source, job)
        if row["title"] and row["company"] and row["apply_url"]:
            out.append(row)
    return out


def indeed_jobs(payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    return load_fixture_jobs("indeed", payload, listing_url=listing_url)


def linkedin_jobs(payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    return load_fixture_jobs("linkedin", payload, listing_url=listing_url)

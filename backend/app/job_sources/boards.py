"""Optional Indeed/LinkedIn/Glassdoor adapters.

Live HTML scraping is out of the Job Source PRD (Greenhouse/Lever only) and is
not implemented. These adapters ingest operator-supplied JSON fixtures when the
feature flag is on and robots/consent checks pass.
"""

from __future__ import annotations

from typing import Any

from app.flags import feature_enabled
from app.job_sources.circuit import allow as circuit_allow
from app.job_sources.robots import can_fetch

ALLOWED_FIXTURE_HOSTS = frozenset({"fixtures.ajas.local", "localhost", "127.0.0.1"})

SOURCE_FLAGS = {
    "indeed": "indeed_adapter",
    "linkedin": "linkedin_adapter",
    "glassdoor": "glassdoor_adapter",
    "wellfound": "wellfound_adapter",
    "workday": "workday_adapter",
    "ziprecruiter": "ziprecruiter_adapter",
    "hired": "hired_adapter",
}


def backoff_seconds(attempt: int, *, base: float = 0.25, cap: float = 8.0) -> float:
    """Exponential backoff for paginated board fetches. Jitter lands in Sprint 10 hardening."""
    if attempt < 0:
        return 0.0
    delay = base * (2**attempt)
    return float(min(cap, delay))


def iter_pages(payload: Any) -> list[list[Any]]:
    """Split a fixture into pages. A flat `jobs` list is treated as a single page."""
    if isinstance(payload, dict) and isinstance(payload.get("pages"), list):
        pages: list[list[Any]] = []
        for page in payload["pages"]:
            if isinstance(page, list):
                pages.append(page)
            elif isinstance(page, dict):
                jobs = page.get("jobs")
                pages.append(jobs if isinstance(jobs, list) else [])
        return pages or [[]]
    if isinstance(payload, list):
        return [payload]
    if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
        return [payload["jobs"]]
    return [[]]


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
        "page": int(job.get("page") or 1),
    }


def load_fixture_jobs(source: str, payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    flag = SOURCE_FLAGS.get(source)
    if not flag or not feature_enabled(flag):
        return []
    if not circuit_allow(source):
        return []
    if listing_url and not can_fetch(listing_url):
        return []
    out: list[dict[str, Any]] = []
    for index, rows in enumerate(iter_pages(payload), start=1):
        _ = backoff_seconds(index - 1)
        if not isinstance(rows, list):
            continue
        for job in rows:
            if not isinstance(job, dict):
                continue
            row = _normalize_row(source, {**job, "page": job.get("page") or index})
            if row["title"] and row["company"] and row["apply_url"]:
                out.append(row)
    return out


def indeed_jobs(payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    return load_fixture_jobs("indeed", payload, listing_url=listing_url)


def linkedin_jobs(payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    return load_fixture_jobs("linkedin", payload, listing_url=listing_url)


def glassdoor_jobs(payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    return load_fixture_jobs("glassdoor", payload, listing_url=listing_url)


def wellfound_jobs(payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    from app.job_sources.wellfound_auth import require_auth

    if not require_auth():
        return []
    return load_fixture_jobs("wellfound", payload, listing_url=listing_url)


def workday_jobs(payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    """Fixture-only. Live Workday HTML scraping is out of the Job Source PRD."""
    return load_fixture_jobs("workday", payload, listing_url=listing_url)


def ziprecruiter_jobs(payload: Any, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    """Fixture-only. Live ZipRecruiter scraping is out of the Job Source PRD."""
    return load_fixture_jobs("ziprecruiter", payload, listing_url=listing_url)

"""Glassdoor ingest executable contract (source of truth).

Glassdoor has no public job-search API. The Partner API (api.glassdoor.com)
closed to new applicants around 2021–2023. Remaining Glassdoor APIs are
employer-facing (post jobs, manage profiles), not listing search.
This module maps the historical Partner envelope plus AJAS fixtures onto
the internal posting schema. Live HTML scraping is not implemented.
``SOURCE_TYPES`` stays {greenhouse, lever}.
"""

from __future__ import annotations

from typing import Any

from app.integrations.board_fields import extract_mapped_field, finish_mapped_job, nested_text
from app.integrations.linkedin_spec import PAGINATION
from app.job_sources.circuit import FAILURE_THRESHOLD as CIRCUIT_FAILURES, OPEN_SECONDS as CIRCUIT_OPEN
from app.job_sources.keys import utc_now

FIELD_MAP: tuple[dict[str, Any], ...] = (
    {
        "glassdoor": "listingId",
        "aliases": ("id", "jobListingId", "jobViewId", "source_posting_id", "jobTitleId"),
        "internal": "sourcePostingId",
        "type": "string",
        "nullable": False,
        "fallback": "canonical_id[:12]",
    },
    {
        "glassdoor": "jobTitle",
        "aliases": ("title", "jobtitle", "name"),
        "internal": "title",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "glassdoor": "employer",
        "aliases": ("company", "companyName", "employerName"),
        "internal": "company",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "glassdoor": "location",
        "aliases": ("jobLocation", "locationName"),
        "internal": "location",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "glassdoor": "jobDescription",
        "aliases": ("description", "body", "content"),
        "internal": "description",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "glassdoor": "jobViewUrl",
        "aliases": ("apply_url", "applyUrl", "url", "postingUrl", "listingUrl", "link"),
        "internal": "postingUrl",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "glassdoor": "jobType",
        "aliases": ("employment_type", "employmentType", "type"),
        "internal": "employmentType",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "glassdoor": "postedDate",
        "aliases": ("postedAt", "posted_at", "datePosted", "discoverDate"),
        "internal": "postedAt",
        "type": "datetime",
        "nullable": True,
        "fallback": "",
    },
    {
        "glassdoor": "salarySource",
        "aliases": ("payPercentile50", "estimatedSalary"),
        "internal": "salaryText",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
)

API_CONTRACT: dict[str, Any] = {
    "publicSearchApi": False,
    "partnerApi": "closed-to-new-applicants",
    "liveScrape": False,
    "acceptedFeeds": (
        "ajas_fixture_json",
        "glassdoor_partner_jobs_envelope",
    ),
    "notes": (
        "Glassdoor Partner Job Search (api.glassdoor.com/api/api.htm action=jobs) is not "
        "available for new integrations. AJAS accepts that historical JSON envelope as a "
        "fixture so a future partner feed can land without a scrape."
    ),
    "docs": ("https://www.glassdoor.com/developer/index.htm",),
}

# Conservative cap: Glassdoor HTML bot-defense is aggressive (Sprint 13 cooldown).
RATE_PLAN: dict[str, dict[str, Any]] = {
    "ingest": {
        "capPerWindow": 20,
        "windowSeconds": 60,
        "jitterSeconds": 0.5,
        "maxAttempts": 4,
        "backoffBaseSeconds": 0.5,
        "backoffCapSeconds": 16.0,
        "circuitFailureThreshold": CIRCUIT_FAILURES,
        "circuitOpenSeconds": CIRCUIT_OPEN,
        "retryStatus": (429, 408, 403, 503, 504),
        "counters": (
            "requests",
            "retries",
            "rate_limited",
            "circuit_open",
            "transient",
            "permanent",
            "captcha",
            "timeout",
            "private_skipped",
            "expired_skipped",
            "deduped",
        ),
    }
}

SECURITY_CHECKLIST: tuple[dict[str, Any], ...] = (
    {
        "id": "no_live_scrape",
        "rule": "Do not fetch glassdoor.com HTML. Ingest only operator-supplied partner/fixture payloads.",
    },
    {
        "id": "block_detection",
        "rule": "403/challenge trips the circuit. Captcha is never bypassed.",
    },
    {
        "id": "access_control",
        "rule": "HTTP routes require JWT; glassdoor_adapter is off by default; SOURCE_TYPES stays greenhouse|lever.",
    },
)


def flatten_partner_job(job: dict[str, Any]) -> dict[str, Any]:
    """Lift nested employer/location objects from the Partner API envelope."""
    row = dict(job)
    employer = job.get("employer")
    if isinstance(employer, dict) and not nested_text(job.get("company")):
        row["company"] = nested_text(employer.get("name")) or nested_text(employer.get("shortName"))
        row["employer"] = row["company"]
    elif isinstance(employer, str):
        row["company"] = employer
    location = job.get("location")
    if isinstance(location, dict):
        row["location"] = nested_text(location.get("name")) or nested_text(location.get("display"))
    salary = job.get("salary") or job.get("estimatedSalary")
    if isinstance(salary, dict):
        low = salary.get("min") or salary.get("percentile10")
        high = salary.get("max") or salary.get("percentile90")
        if low or high:
            row["estimatedSalary"] = f"{low or ''}-{high or ''}".strip("-")
    return row


def unwrap_glassdoor_payload(payload: Any) -> Any:
    """Normalize Partner API `{success, response:{jobs, currentPageNumber}}` plus AJAS pages."""
    if not isinstance(payload, dict):
        return payload
    response = payload.get("response")
    if isinstance(response, dict) and isinstance(response.get("jobs"), list):
        jobs = [flatten_partner_job(job) for job in response["jobs"] if isinstance(job, dict)]
        current = int(response.get("currentPageNumber") or response.get("pageNumber") or 1)
        total = int(response.get("totalNumberOfPages") or current)
        nxt = str(current + 1) if current < total else None
        return {"cursor": str(current), "jobs": jobs, "nextCursor": nxt}
    if isinstance(payload.get("jobs"), list):
        return {**payload, "jobs": [flatten_partner_job(job) if isinstance(job, dict) else job for job in payload["jobs"]]}
    if isinstance(payload.get("pages"), list):
        pages = []
        for page in payload["pages"]:
            if isinstance(page, dict) and isinstance(page.get("jobs"), list):
                pages.append(
                    {
                        **page,
                        "jobs": [flatten_partner_job(job) if isinstance(job, dict) else job for job in page["jobs"]],
                    }
                )
            else:
                pages.append(page)
        return {**payload, "pages": pages}
    return payload


def map_glassdoor_job(job: dict[str, Any]) -> dict[str, Any]:
    flat = flatten_partner_job(job)
    mapped = {row["internal"]: extract_mapped_field(flat, row, source_key="glassdoor") for row in FIELD_MAP}
    salary = mapped.get("salaryText") or ""
    if salary and salary not in (mapped.get("description") or ""):
        mapped["description"] = " ".join(part for part in (mapped.get("description"), salary) if part)
    return finish_mapped_job(mapped, flat)


def spec_bundle() -> dict[str, Any]:
    return {
        "source": "glassdoor",
        "generatedAt": utc_now(),
        "flag": "glassdoor_adapter",
        "liveScrape": False,
        "sourceTypesUnchanged": True,
        "api": API_CONTRACT,
        "fieldMap": [dict(row) for row in FIELD_MAP],
        "ratePlan": RATE_PLAN,
        "pagination": PAGINATION,
        "security": [dict(row) for row in SECURITY_CHECKLIST],
        "http": {
            "ingest": "POST /api/v1/integrations/ingest/glassdoor",
            "spec": "GET /api/v1/integrations/glassdoor/spec",
        },
    }

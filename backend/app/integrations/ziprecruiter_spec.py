"""ZipRecruiter ingest executable contract (source of truth).

ZipRecruiter has no public self-serve job-search API.

- Partner Jobs API (`api.ziprecruiter.com/partner/v0/job`) posts/closes jobs for
  approved ATS partners. It is employer-outbound, not listing search.
- Legacy jobs/v1 (`api.ziprecruiter.com/jobs/v1`) required a publisher API key
  and is not self-serve.
- Publisher XML is a push feed to approved aggregators.

AJAS maps those official envelopes plus AJAS fixtures. Live ziprecruiter.com
HTML scraping is not implemented. ``SOURCE_TYPES`` stays {greenhouse, lever}.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from app.integrations.linkedin_spec import PAGINATION
from app.integrations.listing_fields import (
    extract_mapped_field,
    finish_mapped_job,
    join_location,
    nested_text,
    xml_child_text,
)
from app.job_sources.circuit import FAILURE_THRESHOLD, OPEN_SECONDS
from app.job_sources.keys import utc_now

FIELD_MAP: tuple[dict[str, Any], ...] = (
    {
        "ziprecruiter": "id",
        "aliases": ("job_id", "jobId", "source_posting_id", "referencenumber"),
        "internal": "sourcePostingId",
        "type": "string",
        "nullable": False,
        "fallback": "canonical_id[:12]",
    },
    {
        "ziprecruiter": "name",
        "aliases": ("title", "jobTitle", "job_title"),
        "internal": "title",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "ziprecruiter": "company",
        "aliases": ("companyName", "hiring_company", "employer"),
        "internal": "company",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "ziprecruiter": "location",
        "aliases": ("jobLocation", "formattedLocation"),
        "internal": "location",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "ziprecruiter": "snippet",
        "aliases": ("description", "body", "content", "job_description"),
        "internal": "description",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "ziprecruiter": "url",
        "aliases": ("apply_url", "applyUrl", "job_url", "postingUrl", "link"),
        "internal": "postingUrl",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "ziprecruiter": "employment_type",
        "aliases": ("job_type", "jobType", "type"),
        "internal": "employmentType",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "ziprecruiter": "posted_time",
        "aliases": ("postedAt", "posted_at", "datePosted", "date"),
        "internal": "postedAt",
        "type": "datetime",
        "nullable": True,
        "fallback": "",
    },
    {
        "ziprecruiter": "salaryText",
        "aliases": ("salary", "compensation"),
        "internal": "salaryText",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
)

API_CONTRACT: dict[str, Any] = {
    "publicSearchApi": False,
    "partnerJobsApi": "ats-partner-only",
    "jobsV1SearchApi": "publisher-key-not-self-serve",
    "liveScrape": False,
    "acceptedFeeds": (
        "ajas_fixture_json",
        "ziprecruiter_jobs_v1",
        "ziprecruiter_partner_job",
        "ziprecruiter_publisher_xml",
    ),
    "notes": (
        "ZipRecruiter Partner Jobs API is for posting listings, not searching them. "
        "Legacy jobs/v1 required a publisher key. AJAS accepts those JSON/XML shapes "
        "as operator-supplied fixtures. No live ziprecruiter.com fetch."
    ),
    "docs": (
        "https://www.ziprecruiter.com/partner/documentation/",
        "https://api.ziprecruiter.com/jobs/v1",
        "https://api.ziprecruiter.com/partner/v0/job",
    ),
}

RATE_PLAN: dict[str, dict[str, Any]] = {
    "ingest": {
        "capPerWindow": 20,
        "windowSeconds": 60,
        "jitterSeconds": 0.5,
        "maxAttempts": 4,
        "backoffBaseSeconds": 0.5,
        "backoffCapSeconds": 16.0,
        "circuitFailureThreshold": FAILURE_THRESHOLD,
        "circuitOpenSeconds": OPEN_SECONDS,
        "retryStatus": (429, 408, 503, 504),
        "honorRetryAfter": True,
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
        "rule": "Do not fetch ziprecruiter.com HTML. Ingest only operator-supplied Partner/jobs-v1/fixture payloads.",
    },
    {
        "id": "retry_after",
        "rule": "Honor Retry-After. Never bypass captcha or publisher-key gates.",
    },
    {
        "id": "access_control",
        "rule": "HTTP routes require JWT; ziprecruiter_adapter is off by default; SOURCE_TYPES stays greenhouse|lever.",
    },
)


def parse_publisher_xml(raw: str | bytes) -> list[dict[str, Any]]:
    """Parse ZipRecruiter publisher/import XML. Email nodes are discarded."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    root = ET.fromstring(text)
    rows: list[dict[str, Any]] = []
    for job in root.findall(".//job"):
        city = xml_child_text(job, "city")
        state = xml_child_text(job, "state")
        country = xml_child_text(job, "country")
        rows.append(
            {
                "id": xml_child_text(job, "referencenumber") or xml_child_text(job, "job_reference"),
                "name": xml_child_text(job, "title"),
                "company": xml_child_text(job, "company"),
                "location": join_location(city, state, country),
                "city": city,
                "state": state,
                "country": country,
                "url": xml_child_text(job, "url"),
                "snippet": xml_child_text(job, "description"),
                "employment_type": xml_child_text(job, "jobtype") or xml_child_text(job, "job_type"),
                "posted_time": xml_child_text(job, "date"),
                "salaryText": xml_child_text(job, "salary"),
            }
        )
    return rows


def flatten_ziprecruiter_job(job: dict[str, Any]) -> dict[str, Any]:
    """Lift nested hiring_company / location objects from jobs/v1 and Partner envelopes."""
    row = dict(job)
    hiring = job.get("hiring_company")
    if isinstance(hiring, dict) and not nested_text(job.get("company")):
        row["company"] = nested_text(hiring.get("name")) or nested_text(hiring.get("url"))
        row["hiring_company"] = row["company"]
    elif isinstance(hiring, str):
        row["company"] = hiring
    location = job.get("location")
    if isinstance(location, dict):
        row["location"] = (
            nested_text(location.get("display"))
            or nested_text(location.get("name"))
            or join_location(
                nested_text(location.get("city")),
                nested_text(location.get("state")),
                nested_text(location.get("country")),
            )
        )
    if not nested_text(row.get("location")):
        row["location"] = join_location(
            nested_text(job.get("city")),
            nested_text(job.get("state")),
            nested_text(job.get("country")),
        )
    low = job.get("salary_min_annual") if job.get("salary_min_annual") is not None else job.get("salary_min")
    high = job.get("salary_max_annual") if job.get("salary_max_annual") is not None else job.get("salary_max")
    if low or high:
        row["salaryText"] = f"{low or ''}-{high or ''}".strip("-")
    return row


def unwrap_ziprecruiter_payload(payload: Any) -> Any:
    """Normalize jobs/v1, Partner `{job}`, publisher XML, and AJAS cursor pages."""
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace")
        if text.lstrip().startswith("<"):
            return {"jobs": parse_publisher_xml(text)}
        return payload
    if isinstance(payload, str) and payload.lstrip().startswith("<"):
        return {"jobs": parse_publisher_xml(payload)}
    if not isinstance(payload, dict):
        return payload
    if isinstance(payload.get("job"), dict) and "jobs" not in payload and "pages" not in payload:
        return {"jobs": [flatten_ziprecruiter_job(payload["job"])]}
    if isinstance(payload.get("jobs"), list):
        jobs = [flatten_ziprecruiter_job(job) if isinstance(job, dict) else job for job in payload["jobs"]]
        page = int(payload.get("page") or 1)
        per_page = int(payload.get("jobs_per_page") or payload.get("jobsPerPage") or 0)
        total = int(payload.get("num_paginable_jobs") or payload.get("total") or 0)
        nxt = None
        if per_page and total and page * per_page < total:
            nxt = str(page + 1)
        elif payload.get("next") or payload.get("nextCursor"):
            nxt = str(payload.get("nextCursor") or payload.get("next"))
        return {**payload, "cursor": str(payload.get("cursor") or page), "jobs": jobs, "nextCursor": nxt}
    if isinstance(payload.get("pages"), list):
        pages = []
        for page in payload["pages"]:
            if isinstance(page, dict) and isinstance(page.get("jobs"), list):
                pages.append(
                    {
                        **page,
                        "nextCursor": page.get("nextCursor") or page.get("next"),
                        "jobs": [flatten_ziprecruiter_job(job) if isinstance(job, dict) else job for job in page["jobs"]],
                    }
                )
            else:
                pages.append(page)
        return {**payload, "pages": pages}
    return payload


def map_ziprecruiter_job(job: dict[str, Any]) -> dict[str, Any]:
    flat = flatten_ziprecruiter_job(job)
    mapped = {row["internal"]: extract_mapped_field(flat, row, source_key="ziprecruiter") for row in FIELD_MAP}
    if not mapped.get("location"):
        mapped["location"] = join_location(
            nested_text(flat.get("city")),
            nested_text(flat.get("state")),
            nested_text(flat.get("country")),
        )
    salary = mapped.get("salaryText") or ""
    if salary and salary not in (mapped.get("description") or ""):
        mapped["description"] = " ".join(part for part in (mapped.get("description"), salary) if part)
    return finish_mapped_job(mapped, flat)


def spec_bundle() -> dict[str, Any]:
    return {
        "source": "ziprecruiter",
        "generatedAt": utc_now(),
        "flag": "ziprecruiter_adapter",
        "liveScrape": False,
        "sourceTypesUnchanged": True,
        "api": API_CONTRACT,
        "fieldMap": [dict(row) for row in FIELD_MAP],
        "ratePlan": RATE_PLAN,
        "pagination": PAGINATION,
        "security": [dict(row) for row in SECURITY_CHECKLIST],
        "http": {
            "ingest": "POST /api/v1/integrations/ingest/ziprecruiter",
            "spec": "GET /api/v1/integrations/ziprecruiter/spec",
        },
    }

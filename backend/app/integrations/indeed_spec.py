"""Indeed ingest executable contract (source of truth).

Indeed has no public job-search API. The Publisher API was retired in 2023.
Job Sync XML / Job Sync GraphQL only let ATS partners *push* jobs to Indeed.
This module maps those official feed shapes (plus AJAS fixtures) onto the
internal posting schema. Live HTML scraping is not implemented.
``SOURCE_TYPES`` stays {greenhouse, lever}.
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from app.integrations.board_fields import extract_mapped_field, finish_mapped_job, join_location, xml_child_text
from app.integrations.linkedin_spec import PAGINATION, RATE_PLAN as LINKEDIN_RATE_PLAN, walk_pages
from app.job_sources.circuit import FAILURE_THRESHOLD, OPEN_SECONDS
from app.job_sources.keys import utc_now

FIELD_MAP: tuple[dict[str, Any], ...] = (
    {
        "indeed": "referencenumber",
        "aliases": ("id", "jobid", "jobId", "sourcedPostingId", "source_posting_id", "requisitionid"),
        "internal": "sourcePostingId",
        "type": "string",
        "nullable": False,
        "fallback": "canonical_id[:12]",
    },
    {
        "indeed": "title",
        "aliases": ("jobTitle", "jobtitle"),
        "internal": "title",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "indeed": "company",
        "aliases": ("companyName", "employer", "companyname"),
        "internal": "company",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "indeed": "location",
        "aliases": ("jobLocation", "formattedLocation"),
        "internal": "location",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "indeed": "description",
        "aliases": ("body", "content", "jobDescription", "descriptionHtml"),
        "internal": "description",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "indeed": "url",
        "aliases": ("apply_url", "applyUrl", "postingUrl", "link"),
        "internal": "postingUrl",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "indeed": "jobtype",
        "aliases": ("employment_type", "jobType", "type"),
        "internal": "employmentType",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "indeed": "date",
        "aliases": ("postedAt", "posted_at", "datePosted", "datepublished"),
        "internal": "postedAt",
        "type": "datetime",
        "nullable": True,
        "fallback": "",
    },
    {
        "indeed": "salary",
        "aliases": ("compensation",),
        "internal": "salaryText",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
)

API_CONTRACT: dict[str, Any] = {
    "publicSearchApi": False,
    "publisherApi": "retired-2023",
    "liveScrape": False,
    "acceptedFeeds": (
        "ajas_fixture_json",
        "indeed_job_sync_xml",
        "indeed_job_sync_json",
    ),
    "notes": (
        "Indeed Job Sync XML/API is employer-outbound (ATS → Indeed), not a job-search API. "
        "AJAS accepts the same document shapes as operator-supplied fixtures. "
        "No self-serve credentials exist for reading Indeed SERP listings."
    ),
    "docs": (
        "https://docs.indeed.com/job-sync-xml/xml-feed",
        "https://docs.indeed.com/job-sync-api/job-sync-api-guide",
    ),
}

RATE_PLAN: dict[str, dict[str, Any]] = {
    "ingest": {
        **LINKEDIN_RATE_PLAN["ingest"],
        "capPerWindow": 50,
        "windowSeconds": 60,
        "circuitFailureThreshold": FAILURE_THRESHOLD,
        "circuitOpenSeconds": OPEN_SECONDS,
    }
}

SECURITY_CHECKLIST: tuple[dict[str, Any], ...] = (
    {
        "id": "no_live_scrape",
        "rule": "Do not fetch indeed.com HTML. Ingest only operator-supplied Job Sync / fixture payloads.",
    },
    {
        "id": "pii_minimization",
        "rule": "Job Sync email/contact nodes are dropped. Store FIELD_MAP listing fields only.",
    },
    {
        "id": "access_control",
        "rule": "HTTP routes require JWT; indeed_adapter defaults on (tested); SOURCE_TYPES stays greenhouse|lever.",
    },
    {
        "id": "fail_closed",
        "rule": "Robots/consent, captcha, and missing flags fail closed.",
    },
)


def parse_job_sync_xml(raw: str | bytes) -> list[dict[str, Any]]:
    """Parse Indeed Job Sync XML into listing dicts. Email nodes are discarded."""
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    root = ET.fromstring(text)
    rows: list[dict[str, Any]] = []
    for job in root.findall(".//job"):
        city = xml_child_text(job, "city")
        state = xml_child_text(job, "state")
        country = xml_child_text(job, "country")
        rows.append(
            {
                "referencenumber": xml_child_text(job, "referencenumber"),
                "jobid": xml_child_text(job, "jobid"),
                "requisitionid": xml_child_text(job, "requisitionid"),
                "title": xml_child_text(job, "title"),
                "company": xml_child_text(job, "company"),
                "location": join_location(city, state, country),
                "city": city,
                "state": state,
                "country": country,
                "url": xml_child_text(job, "url"),
                "description": xml_child_text(job, "description"),
                "jobtype": xml_child_text(job, "jobtype"),
                "date": xml_child_text(job, "date"),
                "salary": xml_child_text(job, "salary"),
                "category": xml_child_text(job, "category"),
            }
        )
    return rows


def unwrap_indeed_payload(payload: Any) -> Any:
    """Normalize Job Sync XML/JSON and AJAS fixtures into walk_pages input."""
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace")
        if text.lstrip().startswith("<"):
            return {"jobs": parse_job_sync_xml(text)}
        return payload
    if isinstance(payload, str) and payload.lstrip().startswith("<"):
        return {"jobs": parse_job_sync_xml(payload)}
    if not isinstance(payload, dict):
        return payload
    sourced = payload.get("sourcedJobPostings")
    if isinstance(sourced, list):
        return {"jobs": sourced, "cursor": payload.get("cursor"), "nextCursor": payload.get("nextCursor")}
    data = payload.get("data")
    if isinstance(data, dict):
        ingest = data.get("jobsIngest") if isinstance(data.get("jobsIngest"), dict) else data
        for key in ("sourcedJobPostings", "results", "jobPostings", "jobs"):
            rows = ingest.get(key) if isinstance(ingest, dict) else None
            if isinstance(rows, list):
                return {"jobs": rows}
    return payload


def map_indeed_job(job: dict[str, Any]) -> dict[str, Any]:
    mapped = {row["internal"]: extract_mapped_field(job, row, source_key="indeed") for row in FIELD_MAP}
    if not mapped.get("location"):
        mapped["location"] = join_location(
            str(job.get("city") or ""),
            str(job.get("state") or ""),
            str(job.get("country") or ""),
        )
    salary = mapped.get("salaryText") or ""
    if salary and salary not in (mapped.get("description") or ""):
        mapped["description"] = " ".join(part for part in (mapped.get("description"), salary) if part)
    return finish_mapped_job(mapped, job)


def spec_bundle() -> dict[str, Any]:
    return {
        "source": "indeed",
        "generatedAt": utc_now(),
        "flag": "indeed_adapter",
        "liveScrape": False,
        "sourceTypesUnchanged": True,
        "api": API_CONTRACT,
        "fieldMap": [dict(row) for row in FIELD_MAP],
        "ratePlan": RATE_PLAN,
        "pagination": PAGINATION,
        "security": [dict(row) for row in SECURITY_CHECKLIST],
        "http": {
            "ingest": "POST /api/v1/integrations/ingest/indeed",
            "spec": "GET /api/v1/integrations/indeed/spec",
        },
    }

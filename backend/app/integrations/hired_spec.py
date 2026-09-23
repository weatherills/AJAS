"""Hired ingest executable contract (source of truth).

Hired is a recruiter marketplace, not a public job board. There is no
self-serve job-search API. ATS/partner integrations are outbound (post a role
to Hired), not listing search. Historical recruiter JSON used `positions` and
candidate `matches` envelopes, gated by session tokens and CAPTCHA.

AJAS maps those envelopes plus AJAS fixtures. Live hired.com HTML scraping
and CAPTCHA solving are not implemented. ``SOURCE_TYPES`` stays {greenhouse, lever}.
A Hired API token (`HIRED_API_TOKEN` / `remember_token`) is required; captcha
fixtures fail closed as `needs_manual`.
"""

from __future__ import annotations

from typing import Any

from app.integrations.linkedin_spec import PAGINATION, RATE_PLAN as LINKEDIN_RATE_PLAN
from app.integrations.listing_fields import (
    extract_mapped_field,
    finish_mapped_job,
    join_location,
    nested_text,
    strip_pii,
)
from app.job_sources.circuit import FAILURE_THRESHOLD, OPEN_SECONDS
from app.job_sources.keys import utc_now

FIELD_MAP: tuple[dict[str, Any], ...] = (
    {
        "hired": "id",
        "aliases": ("position_id", "positionId", "source_posting_id", "uuid"),
        "internal": "sourcePostingId",
        "type": "string",
        "nullable": False,
        "fallback": "canonical_id[:12]",
    },
    {
        "hired": "title",
        "aliases": ("jobTitle", "name", "role"),
        "internal": "title",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "hired": "company",
        "aliases": ("companyName", "company_name", "employer"),
        "internal": "company",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "hired": "location",
        "aliases": ("jobLocation", "formattedLocation"),
        "internal": "location",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "hired": "description",
        "aliases": ("body", "content", "jobDescription", "snippet"),
        "internal": "description",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "hired": "apply_url",
        "aliases": ("url", "public_url", "publicUrl", "postingUrl", "link"),
        "internal": "postingUrl",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "hired": "employment_type",
        "aliases": ("employmentType", "jobType", "type", "commitment"),
        "internal": "employmentType",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "hired": "posted_at",
        "aliases": ("postedAt", "created_at", "createdAt", "datePosted"),
        "internal": "postedAt",
        "type": "datetime",
        "nullable": True,
        "fallback": "",
    },
    {
        "hired": "salaryText",
        "aliases": ("salary", "compensation"),
        "internal": "salaryText",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
)

API_CONTRACT: dict[str, Any] = {
    "publicSearchApi": False,
    "marketplace": "recruiter-candidate-matching",
    "atsPartnerApi": "employer-outbound-only",
    "liveScrape": False,
    "tokenRequired": True,
    "captcha": "fail-closed-needs_manual",
    "acceptedFeeds": (
        "ajas_fixture_json",
        "hired_positions",
        "hired_matches",
    ),
    "notes": (
        "Hired has no public job-search API. Recruiter positions/matches JSON is "
        "session-gated. AJAS accepts those envelopes as operator-supplied fixtures "
        "when HIRED_API_TOKEN is set. CAPTCHA never bypasses. No live hired.com fetch."
    ),
    "docs": (
        "https://hired.com/",
        "https://hired.com/ats-partners",
    ),
}

RATE_PLAN: dict[str, dict[str, Any]] = {
    "ingest": {
        **LINKEDIN_RATE_PLAN["ingest"],
        "capPerWindow": 20,
        "windowSeconds": 60,
        "circuitFailureThreshold": FAILURE_THRESHOLD,
        "circuitOpenSeconds": OPEN_SECONDS,
        "retryStatus": (429, 408, 403, 503, 504),
    }
}

SECURITY_CHECKLIST: tuple[dict[str, Any], ...] = (
    {
        "id": "no_live_scrape",
        "rule": "Do not fetch hired.com HTML. Ingest only operator-supplied positions/matches/fixture payloads.",
    },
    {
        "id": "token_and_captcha",
        "rule": "Require HIRED_API_TOKEN. CAPTCHA and missing tokens fail closed (needs_manual / needs_auth). Never bypass.",
    },
    {
        "id": "pii_minimization",
        "rule": "Drop candidate/contact email fields from matches envelopes. Store FIELD_MAP listing fields only.",
    },
    {
        "id": "access_control",
        "rule": "HTTP routes require JWT; hired_adapter defaults on (tested); SOURCE_TYPES stays greenhouse|lever.",
    },
)


def _salary_text(job: dict[str, Any]) -> str:
    direct = nested_text(job.get("salaryText")) or nested_text(job.get("salary"))
    if direct:
        return direct
    comp = job.get("compensation")
    if isinstance(comp, dict):
        low = nested_text(comp.get("min") or comp.get("minValue") or comp.get("salary_min"))
        high = nested_text(comp.get("max") or comp.get("maxValue") or comp.get("salary_max"))
        if low or high:
            return f"{low}-{high}".strip("-")
    return ""


def flatten_hired_job(job: dict[str, Any]) -> dict[str, Any]:
    """Lift nested company/location/position objects. Candidate emails are dropped."""
    source = strip_pii(dict(job))
    nested_pos = job.get("position") if isinstance(job.get("position"), dict) else None
    if nested_pos and not nested_text(job.get("title")):
        source = {**strip_pii(dict(nested_pos)), **{k: v for k, v in source.items() if k != "position"}}
        job = {**nested_pos, **job}
    row = dict(source)
    company = job.get("company")
    if isinstance(company, dict) and not nested_text(row.get("company")):
        row["company"] = nested_text(company.get("name")) or nested_text(company.get("displayName"))
    elif isinstance(company, str):
        row["company"] = company
    if not nested_text(row.get("company")):
        row["company"] = nested_text(job.get("company_name")) or nested_text(job.get("companyName"))
    location = job.get("location")
    if isinstance(location, dict):
        row["location"] = (
            nested_text(location.get("display"))
            or nested_text(location.get("name"))
            or join_location(
                nested_text(location.get("city")),
                nested_text(location.get("state") or location.get("region")),
                nested_text(location.get("country")),
            )
        )
    if not nested_text(row.get("location")):
        row["location"] = join_location(
            nested_text(job.get("city")),
            nested_text(job.get("state")),
            nested_text(job.get("country")),
        )
    salary = _salary_text(job) or _salary_text(row)
    if salary:
        row["salaryText"] = salary
    url = (
        nested_text(row.get("apply_url"))
        or nested_text(row.get("public_url"))
        or nested_text(row.get("publicUrl"))
        or nested_text(row.get("url"))
        or nested_text(row.get("postingUrl"))
        or nested_text(row.get("link"))
    )
    posting_id = nested_text(row.get("id")) or nested_text(row.get("position_id")) or nested_text(row.get("positionId"))
    if not url and posting_id:
        url = f"https://hired.com/jobs/{posting_id}"
    row["apply_url"] = url
    row["url"] = url
    return strip_pii(row)


def _page_meta(envelope: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, Any]:
    page_info = envelope.get("pageInfo") if isinstance(envelope.get("pageInfo"), dict) else {}
    nxt = envelope.get("nextCursor") or envelope.get("next")
    if not nxt and page_info.get("hasNextPage"):
        nxt = page_info.get("endCursor") or page_info.get("cursor")
    cursor = envelope.get("cursor") or page_info.get("startCursor") or "p0"
    return {"cursor": str(cursor), "jobs": jobs, "nextCursor": str(nxt) if nxt else None}


def unwrap_hired_payload(payload: Any) -> Any:
    """Normalize positions/matches envelopes plus AJAS cursor pages."""
    if not isinstance(payload, dict):
        return payload
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if isinstance(data.get("position"), dict) and "jobs" not in data and "positions" not in data and "matches" not in data:
        return {"jobs": [flatten_hired_job(data["position"])]}
    if isinstance(data.get("positions"), list) and "jobs" not in data:
        jobs = [flatten_hired_job(job) for job in data["positions"] if isinstance(job, dict)]
        return {**_page_meta(data, jobs), **({} if data is payload else {})}
    if isinstance(data.get("matches"), list) and "jobs" not in data:
        jobs = [flatten_hired_job(job) for job in data["matches"] if isinstance(job, dict)]
        return _page_meta(data, jobs)
    if isinstance(payload.get("jobs"), list):
        return {**payload, "jobs": [flatten_hired_job(job) if isinstance(job, dict) else job for job in payload["jobs"]]}
    if isinstance(payload.get("pages"), list):
        pages = []
        for page in payload["pages"]:
            if not isinstance(page, dict):
                pages.append(page)
                continue
            rows = page.get("jobs")
            if not isinstance(rows, list):
                rows = page.get("positions") if isinstance(page.get("positions"), list) else page.get("matches")
            if isinstance(rows, list):
                pages.append({**page, "jobs": [flatten_hired_job(job) if isinstance(job, dict) else job for job in rows]})
            else:
                pages.append(page)
        return {**payload, "pages": pages}
    return payload


def map_hired_job(job: dict[str, Any]) -> dict[str, Any]:
    flat = flatten_hired_job(job)
    mapped = {row["internal"]: extract_mapped_field(flat, row, source_key="hired") for row in FIELD_MAP}
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
        "source": "hired",
        "generatedAt": utc_now(),
        "flag": "hired_adapter",
        "liveScrape": False,
        "sourceTypesUnchanged": True,
        "api": API_CONTRACT,
        "fieldMap": [dict(row) for row in FIELD_MAP],
        "ratePlan": RATE_PLAN,
        "pagination": PAGINATION,
        "security": [dict(row) for row in SECURITY_CHECKLIST],
        "http": {
            "ingest": "POST /api/v1/integrations/ingest/hired",
            "spec": "GET /api/v1/integrations/hired/spec",
        },
    }

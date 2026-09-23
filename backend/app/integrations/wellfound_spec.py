"""Wellfound (AngelList) ingest executable contract (source of truth).

Wellfound has no public job-search API. `api.angel.co` is retired. The
consumer GraphQL (`JobSearchResults` / `JobSearchResultsX`) is session and
CSRF/bot gated. Recruiter MCP OAuth is not job search.

AJAS maps GraphQL job-search and startup-listing envelopes plus AJAS fixtures.
Live wellfound.com HTML scraping is not implemented. ``SOURCE_TYPES`` stays
{greenhouse, lever}. A token (`WELLFOUND_API_TOKEN` / `remember_token`) is required.
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
        "wellfound": "id",
        "aliases": ("jobId", "source_posting_id", "slug", "uuid"),
        "internal": "sourcePostingId",
        "type": "string",
        "nullable": False,
        "fallback": "canonical_id[:12]",
    },
    {
        "wellfound": "title",
        "aliases": ("jobTitle", "name", "role"),
        "internal": "title",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "wellfound": "company",
        "aliases": ("companyName", "startupName", "employer"),
        "internal": "company",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "wellfound": "location",
        "aliases": ("jobLocation", "formattedLocation", "locationNames"),
        "internal": "location",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "wellfound": "description",
        "aliases": ("descriptionSnippet", "body", "content", "jobDescription"),
        "internal": "description",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "wellfound": "apply_url",
        "aliases": ("url", "postingUrl", "listingUrl", "primaryRoleListingUrl", "link"),
        "internal": "postingUrl",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "wellfound": "commitment",
        "aliases": ("employment_type", "employmentType", "jobType", "type"),
        "internal": "employmentType",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "wellfound": "liveStartAt",
        "aliases": ("postedAt", "posted_at", "publishedAt", "datePosted"),
        "internal": "postedAt",
        "type": "datetime",
        "nullable": True,
        "fallback": "",
    },
    {
        "wellfound": "salaryText",
        "aliases": ("salary", "compensation"),
        "internal": "salaryText",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
)

API_CONTRACT: dict[str, Any] = {
    "publicSearchApi": False,
    "angelListRest": "retired",
    "consumerGraphql": "session-csrf-bot-gated",
    "recruiterMcp": "oauth-not-job-search",
    "liveScrape": False,
    "tokenRequired": True,
    "acceptedFeeds": (
        "ajas_fixture_json",
        "wellfound_graphql_job_search",
        "wellfound_startup_listings",
    ),
    "notes": (
        "Wellfound has no public listing API. GraphQL JobSearchResults / JobSearchResultsX "
        "and startup job listings are accepted as operator-supplied fixtures when "
        "WELLFOUND_API_TOKEN is set. No live wellfound.com or api.angel.co fetch."
    ),
    "docs": (
        "https://wellfound.com/",
        "https://wellfound.com/graphql",
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
        "rule": "Do not fetch wellfound.com or api.angel.co. Ingest only operator-supplied GraphQL/fixture payloads.",
    },
    {
        "id": "token_required",
        "rule": "Require WELLFOUND_API_TOKEN. Missing tokens fail closed as needs_auth.",
    },
    {
        "id": "pii_minimization",
        "rule": "Drop recruiter/candidate email fields. Store FIELD_MAP listing fields only.",
    },
    {
        "id": "access_control",
        "rule": "HTTP routes require JWT; wellfound_adapter is off by default; SOURCE_TYPES stays greenhouse|lever.",
    },
)

_SEARCH_KEYS = ("jobSearchResults", "JobSearchResultsX", "jobSearchResultsX", "job_search_results")


def _salary_text(job: dict[str, Any]) -> str:
    direct = nested_text(job.get("salaryText")) or nested_text(job.get("salary"))
    if direct:
        return direct
    comp = job.get("compensation")
    if isinstance(comp, dict):
        low = nested_text(comp.get("min") or comp.get("minValue") or comp.get("equityMin"))
        high = nested_text(comp.get("max") or comp.get("maxValue") or comp.get("equityMax"))
        currency = nested_text(comp.get("currency") or comp.get("currencyCode"))
        span = f"{low}-{high}".strip("-")
        if span and currency:
            return f"{currency} {span}"
        return span
    return ""


def _company_bits(job: dict[str, Any], *, company: str = "", company_slug: str = "") -> tuple[str, str]:
    startup = job.get("startup") or job.get("company") or job.get("organization")
    if isinstance(startup, dict):
        company = company or nested_text(startup.get("name")) or nested_text(startup.get("displayName"))
        company_slug = company_slug or nested_text(startup.get("slug"))
    elif isinstance(startup, str):
        company = company or startup
    if not company:
        company = nested_text(job.get("companyName")) or nested_text(job.get("startupName"))
    return company, company_slug


def _apply_url(job: dict[str, Any], *, company_slug: str = "") -> str:
    url = (
        nested_text(job.get("apply_url"))
        or nested_text(job.get("url"))
        or nested_text(job.get("listingUrl"))
        or nested_text(job.get("primaryRoleListingUrl"))
        or nested_text(job.get("postingUrl"))
        or nested_text(job.get("link"))
    )
    if url:
        return url
    job_id = nested_text(job.get("id")) or nested_text(job.get("slug"))
    slug = nested_text(job.get("slug"))
    if company_slug and (slug or job_id):
        return f"https://wellfound.com/company/{company_slug}/jobs/{slug or job_id}"
    if job_id:
        return f"https://wellfound.com/jobs/{job_id}"
    return ""


def flatten_wellfound_job(job: dict[str, Any], *, company: str = "", company_slug: str = "") -> dict[str, Any]:
    """Lift GraphQL startup/company/location fields. Emails are dropped."""
    row = strip_pii(dict(job))
    company, company_slug = _company_bits(job, company=company, company_slug=company_slug)
    if company:
        row["company"] = company
    if company_slug:
        row["companySlug"] = company_slug
    names = job.get("locationNames") or job.get("locations")
    if isinstance(names, list) and names:
        row["location"] = ", ".join(part for part in (nested_text(item) for item in names) if part)
    elif isinstance(job.get("location"), dict):
        loc = job["location"]
        row["location"] = join_location(
            nested_text(loc.get("city")),
            nested_text(loc.get("state") or loc.get("region")),
            nested_text(loc.get("country")),
        ) or nested_text(loc.get("display")) or nested_text(loc.get("name"))
    if not nested_text(row.get("location")) and job.get("remote") is True:
        row["location"] = "Remote"
    if not nested_text(row.get("description")):
        row["description"] = nested_text(job.get("descriptionSnippet")) or nested_text(job.get("descriptionHtml"))
    if not nested_text(row.get("employment_type")) and not nested_text(row.get("commitment")):
        row["commitment"] = nested_text(job.get("commitment"))
    salary = _salary_text(job)
    if salary:
        row["salaryText"] = salary
    url = _apply_url(row, company_slug=company_slug)
    row["apply_url"] = url
    row["url"] = url
    return strip_pii(row)


def _nodes(connection: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("jobs", "jobListings", "listings", "results", "nodes"):
        rows = connection.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    edges = connection.get("edges")
    if isinstance(edges, list):
        nodes: list[dict[str, Any]] = []
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            node = edge.get("node") if isinstance(edge.get("node"), dict) else edge
            if isinstance(node, dict):
                nodes.append(node)
        return nodes
    return []


def _page_meta(connection: dict[str, Any], jobs: list[dict[str, Any]]) -> dict[str, Any]:
    page_info = connection.get("pageInfo") if isinstance(connection.get("pageInfo"), dict) else {}
    nxt = connection.get("nextCursor") or connection.get("next")
    if not nxt and page_info.get("hasNextPage"):
        nxt = page_info.get("endCursor") or page_info.get("cursor")
    cursor = connection.get("cursor") or page_info.get("startCursor") or "p0"
    return {"cursor": str(cursor), "jobs": jobs, "nextCursor": str(nxt) if nxt else None}


def _graphql_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _search_connection(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = _graphql_data(payload)
    talent = data.get("talent") if isinstance(data.get("talent"), dict) else {}
    for key in _SEARCH_KEYS:
        if isinstance(talent.get(key), dict):
            return talent[key]
        if isinstance(data.get(key), dict):
            return data[key]
    jobs_root = data.get("jobs")
    if isinstance(jobs_root, dict):
        nested = jobs_root.get("jobSearchResults") if isinstance(jobs_root.get("jobSearchResults"), dict) else None
        if nested:
            return nested
        if isinstance(jobs_root.get("edges"), list) or isinstance(jobs_root.get("nodes"), list):
            return jobs_root
    return None


def _startup_envelope(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = _graphql_data(payload)
    startup = data.get("startup") if isinstance(data.get("startup"), dict) else payload.get("startup")
    if isinstance(startup, dict):
        listings = startup.get("jobs") or startup.get("jobListings") or startup.get("listings")
        if isinstance(listings, list):
            return startup
    return None


def unwrap_wellfound_payload(payload: Any) -> Any:
    """Normalize GraphQL JobSearchResultsX, startup listings, and AJAS pages."""
    if not isinstance(payload, dict):
        return payload
    connection = _search_connection(payload)
    if connection is not None:
        jobs = [flatten_wellfound_job(job) for job in _nodes(connection)]
        return _page_meta(connection, jobs)
    startup = _startup_envelope(payload)
    if startup is not None:
        company = nested_text(startup.get("name"))
        slug = nested_text(startup.get("slug"))
        listings = startup.get("jobs") or startup.get("jobListings") or startup.get("listings") or []
        jobs = [
            flatten_wellfound_job(job, company=company, company_slug=slug)
            for job in listings
            if isinstance(job, dict)
        ]
        return _page_meta(startup, jobs)
    if isinstance(payload.get("jobs"), list):
        return {
            **payload,
            "jobs": [flatten_wellfound_job(job) if isinstance(job, dict) else job for job in payload["jobs"]],
        }
    if isinstance(payload.get("pages"), list):
        pages = []
        for page in payload["pages"]:
            if not isinstance(page, dict):
                pages.append(page)
                continue
            nested = _search_connection(page) or _startup_envelope(page)
            if nested is not None:
                company = nested_text(nested.get("name"))
                slug = nested_text(nested.get("slug"))
                pages.append(
                    {
                        **page,
                        "jobs": [
                            flatten_wellfound_job(job, company=company, company_slug=slug)
                            for job in _nodes(nested)
                        ],
                    }
                )
                continue
            rows = page.get("jobs")
            if isinstance(rows, list):
                pages.append(
                    {
                        **page,
                        "jobs": [flatten_wellfound_job(job) if isinstance(job, dict) else job for job in rows],
                    }
                )
            else:
                pages.append(page)
        return {**payload, "pages": pages}
    return payload


def map_wellfound_job(job: dict[str, Any]) -> dict[str, Any]:
    flat = flatten_wellfound_job(job)
    mapped = {row["internal"]: extract_mapped_field(flat, row, source_key="wellfound") for row in FIELD_MAP}
    if not mapped.get("location"):
        mapped["location"] = join_location(
            nested_text(flat.get("city")),
            nested_text(flat.get("state")),
            nested_text(flat.get("country")),
        ) or ("Remote" if flat.get("remote") is True else "")
    salary = mapped.get("salaryText") or ""
    if salary and salary not in (mapped.get("description") or ""):
        mapped["description"] = " ".join(part for part in (mapped.get("description"), salary) if part)
    return finish_mapped_job(mapped, flat)


def spec_bundle() -> dict[str, Any]:
    return {
        "source": "wellfound",
        "generatedAt": utc_now(),
        "flag": "wellfound_adapter",
        "liveScrape": False,
        "sourceTypesUnchanged": True,
        "api": API_CONTRACT,
        "fieldMap": [dict(row) for row in FIELD_MAP],
        "ratePlan": RATE_PLAN,
        "pagination": PAGINATION,
        "security": [dict(row) for row in SECURITY_CHECKLIST],
        "http": {
            "ingest": "POST /api/v1/integrations/ingest/wellfound",
            "spec": "GET /api/v1/integrations/wellfound/spec",
        },
    }

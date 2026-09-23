"""Workday ingest executable contract (source of truth).

Workday's official REST/SOAP APIs are tenant-customer only (HCM/Recruiting).
Public career sites expose an undocumented CXS JSON API:

    POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

AJAS does not call that endpoint live (Akamai bot-management, undocumented
contract, Job Source PRD keeps SOURCE_TYPES as greenhouse|lever). This module
maps CXS list/detail envelopes plus AJAS fixtures onto the internal posting
schema. Live HTML scraping is not implemented.
"""

from __future__ import annotations

from typing import Any

from app.integrations.linkedin_spec import PAGINATION, RATE_PLAN as LINKEDIN_RATE_PLAN
from app.integrations.listing_fields import extract_mapped_field, finish_mapped_job, join_location, nested_text
from app.job_sources.circuit import FAILURE_THRESHOLD, OPEN_SECONDS
from app.job_sources.keys import utc_now

FIELD_MAP: tuple[dict[str, Any], ...] = (
    {
        "workday": "jobReqId",
        "aliases": ("id", "jobPostingId", "source_posting_id", "requisitionId"),
        "internal": "sourcePostingId",
        "type": "string",
        "nullable": False,
        "fallback": "canonical_id[:12]",
    },
    {
        "workday": "title",
        "aliases": ("jobTitle", "name"),
        "internal": "title",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "workday": "company",
        "aliases": ("companyName", "tenantName", "hiringOrganization"),
        "internal": "company",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "workday": "locationsText",
        "aliases": ("location", "jobLocation"),
        "internal": "location",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "workday": "jobDescription",
        "aliases": ("description", "body", "content"),
        "internal": "description",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "workday": "externalUrl",
        "aliases": ("apply_url", "applyUrl", "url", "postingUrl", "link"),
        "internal": "postingUrl",
        "type": "string",
        "nullable": False,
        "fallback": None,
    },
    {
        "workday": "timeType",
        "aliases": ("employment_type", "employmentType", "type"),
        "internal": "employmentType",
        "type": "string",
        "nullable": True,
        "fallback": "",
    },
    {
        "workday": "startDate",
        "aliases": ("postedAt", "posted_at", "postedOn", "datePosted"),
        "internal": "postedAt",
        "type": "datetime",
        "nullable": True,
        "fallback": "",
    },
)

API_CONTRACT: dict[str, Any] = {
    "publicSearchApi": False,
    "officialRestSoap": "tenant-customer-only",
    "cxsCareerSiteJson": "undocumented-unauthenticated-per-tenant",
    "liveScrape": False,
    "acceptedFeeds": (
        "ajas_fixture_json",
        "workday_cxs_job_postings",
        "workday_cxs_job_posting_info",
    ),
    "notes": (
        "Workday HCM REST/SOAP is not available to aggregators. "
        "Career-site CXS JSON (POST /wday/cxs/{tenant}/{site}/jobs, limit 20) is the "
        "page's own undocumented API. AJAS accepts that envelope as an operator-supplied "
        "fixture and does not fetch myworkdayjobs.com."
    ),
    "docs": (
        "https://community.workday.com/",
        "https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs",
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
        "rule": "Do not fetch myworkdayjobs.com. Ingest only operator-supplied CXS/fixture payloads.",
    },
    {
        "id": "access_control",
        "rule": "HTTP routes require JWT; workday_adapter defaults on (tested); SOURCE_TYPES stays greenhouse|lever.",
    },
    {
        "id": "fail_closed",
        "rule": "Robots/consent, captcha, and missing flags fail closed.",
    },
)


def _meta(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "company": nested_text(payload.get("company"))
        or nested_text(payload.get("tenantName"))
        or nested_text(payload.get("hiringOrganization")),
        "host": nested_text(payload.get("host")) or nested_text(payload.get("hostname")),
        "site": nested_text(payload.get("site")) or nested_text(payload.get("careerSite")),
        "locale": nested_text(payload.get("locale")) or "en-US",
    }


def _career_url(*, host: str, site: str, path: str, locale: str) -> str:
    if not host or not path:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    site = site.strip("/")
    locale = (locale or "en-US").strip("/")
    if site:
        return f"https://{host}/{locale}/{site}{path}"
    return f"https://{host}{path}"


def flatten_cxs_job(job: dict[str, Any], *, meta: dict[str, str] | None = None) -> dict[str, Any]:
    """Lift CXS list + jobPostingInfo detail fields onto a flat listing dict."""
    info = job.get("jobPostingInfo") if isinstance(job.get("jobPostingInfo"), dict) else {}
    row: dict[str, Any] = {**info, **{key: value for key, value in job.items() if key != "jobPostingInfo"}}
    extra = meta or {}
    bullets = row.get("bulletFields")
    if not row.get("jobReqId") and isinstance(bullets, list) and bullets:
        row["jobReqId"] = str(bullets[0])
    if not row.get("id"):
        row["id"] = row.get("jobReqId") or row.get("jobPostingId") or ""
    if not nested_text(row.get("company")):
        row["company"] = extra.get("company") or ""
    if not nested_text(row.get("location")) and not nested_text(row.get("locationsText")):
        loc = row.get("jobRequisitionLocation")
        if isinstance(loc, dict):
            row["location"] = nested_text(loc.get("descriptor")) or nested_text(loc.get("country"))
    path = nested_text(row.get("externalPath"))
    if not nested_text(row.get("externalUrl")) and not nested_text(row.get("apply_url")) and not nested_text(row.get("url")):
        row["externalUrl"] = _career_url(
            host=extra.get("host") or "",
            site=extra.get("site") or "",
            path=path,
            locale=extra.get("locale") or "en-US",
        )
    return row


def unwrap_workday_payload(payload: Any) -> Any:
    """Normalize CXS `{total, jobPostings}` / `{jobPostingInfo}` plus AJAS pages."""
    if not isinstance(payload, dict):
        return payload
    meta = _meta(payload)
    if isinstance(payload.get("jobPostingInfo"), dict) and "jobPostings" not in payload:
        return {"jobs": [flatten_cxs_job(payload, meta=meta)]}
    if isinstance(payload.get("jobPostings"), list):
        jobs = [flatten_cxs_job(job, meta=meta) for job in payload["jobPostings"] if isinstance(job, dict)]
        total = int(payload.get("total") or len(jobs))
        limit = int(payload.get("limit") or 20)
        offset = int(payload.get("offset") or 0)
        nxt = str(offset + limit) if offset + len(jobs) < total else None
        return {"cursor": str(offset), "jobs": jobs, "nextCursor": nxt}
    if isinstance(payload.get("jobs"), list):
        return {**payload, "jobs": [flatten_cxs_job(job, meta=meta) if isinstance(job, dict) else job for job in payload["jobs"]]}
    if isinstance(payload.get("pages"), list):
        pages = []
        for page in payload["pages"]:
            if not isinstance(page, dict):
                pages.append(page)
                continue
            rows = page.get("jobPostings") if isinstance(page.get("jobPostings"), list) else page.get("jobs")
            if isinstance(rows, list):
                pages.append({**page, "jobs": [flatten_cxs_job(job, meta=_meta({**meta, **page})) if isinstance(job, dict) else job for job in rows]})
            else:
                pages.append(page)
        return {**payload, "pages": pages}
    return payload


def map_workday_job(job: dict[str, Any]) -> dict[str, Any]:
    flat = flatten_cxs_job(job)
    mapped = {row["internal"]: extract_mapped_field(flat, row, source_key="workday") for row in FIELD_MAP}
    if not mapped.get("location"):
        mapped["location"] = join_location(
            nested_text(flat.get("city")),
            nested_text(flat.get("state")),
            nested_text(flat.get("country")),
        ) or nested_text(flat.get("locationsText"))
    return finish_mapped_job(mapped, flat)


def spec_bundle() -> dict[str, Any]:
    return {
        "source": "workday",
        "generatedAt": utc_now(),
        "flag": "workday_adapter",
        "liveScrape": False,
        "sourceTypesUnchanged": True,
        "api": API_CONTRACT,
        "fieldMap": [dict(row) for row in FIELD_MAP],
        "ratePlan": RATE_PLAN,
        "pagination": PAGINATION,
        "security": [dict(row) for row in SECURITY_CHECKLIST],
        "http": {
            "ingest": "POST /api/v1/integrations/ingest/workday",
            "spec": "GET /api/v1/integrations/workday/spec",
        },
    }

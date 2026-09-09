"""Normalize Greenhouse/Lever payloads into ingest fields."""

from __future__ import annotations

import html
import json
import re
from typing import Any

_EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
_TAG = re.compile(r"<[^>]+>")
MAX_BODY_CHARS = 80_000


def strip_html(value: str | None) -> str:
    text = html.unescape(_TAG.sub(" ", value or ""))
    return " ".join(text.split())


def redact_emails(value: str | None) -> str:
    return _EMAIL.sub("[redacted]", value or "")


def truncate(value: str, limit: int = MAX_BODY_CHARS) -> str:
    if len(value) <= limit:
        return value
    return value[:limit]


def payload_dumps(data: Any) -> str:
    return json.dumps(data, sort_keys=True, default=str)


def _first(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("name") or value.get("text")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return ""


def greenhouse_list_jobs(payload: Any) -> tuple[list[dict], str | None]:
    if isinstance(payload, dict):
        jobs = payload.get("jobs") or []
        next_page = None
        meta = payload.get("meta") or {}
        current = payload.get("page") or meta.get("page")
        if isinstance(jobs, list) and jobs:
            page = int(current or 1)
            next_page = str(page + 1)
        return list(jobs) if isinstance(jobs, list) else [], next_page
    if isinstance(payload, list):
        return payload, None
    return [], None


def greenhouse_job(job: dict) -> dict:
    location = ""
    loc = job.get("location")
    if isinstance(loc, dict):
        location = _first(loc.get("name"))
    elif isinstance(loc, str):
        location = loc
    departments = job.get("departments") or []
    dept = ""
    if isinstance(departments, list) and departments:
        dept = _first(departments[0])
    html_body = _first(job.get("content"), job.get("content_html"))
    text = redact_emails(strip_html(html_body or _first(job.get("content_plain"))))
    apply_url = _first(job.get("absolute_url"), job.get("apply_url"), job.get("url"))
    return {
        "source_posting_id": str(job.get("id") or ""),
        "title": _first(job.get("title")),
        "location": location,
        "employment_type": _first(job.get("employment_type"), job.get("type")),
        "body": truncate(text),
        "apply_url": apply_url,
        "company": _first(job.get("company_name"), job.get("company")),
        "department": dept,
        "html": html_body,
    }


def lever_list_jobs(payload: Any) -> tuple[list[dict], str | None]:
    jobs = payload if isinstance(payload, list) else payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(jobs, list):
        return [], None
    return jobs, (str(len(jobs)) if jobs else None)


def lever_job(job: dict) -> dict:
    categories = job.get("categories") if isinstance(job.get("categories"), dict) else {}
    html_body = _first(job.get("description"), job.get("descriptionHtml"), job.get("content"))
    plain = _first(job.get("descriptionPlain"), job.get("description_plain"))
    text = redact_emails(strip_html(html_body or plain))
    apply_url = _first(job.get("applyUrl"), job.get("hostedUrl"), job.get("hosted_url"))
    return {
        "source_posting_id": str(job.get("id") or ""),
        "title": _first(job.get("text"), job.get("title")),
        "location": _first(categories.get("location"), job.get("location")),
        "employment_type": _first(categories.get("commitment"), job.get("commitment")),
        "body": truncate(text),
        "apply_url": apply_url,
        "company": _first(job.get("company"), categories.get("department")),
        "department": _first(categories.get("team"), categories.get("department")),
        "html": html_body or plain,
    }

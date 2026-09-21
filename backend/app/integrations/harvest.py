"""Greenhouse Harvest-style application status reader.

Public board crawl stays on boards-api.greenhouse.io. This module polls
Harvest applications for status (flag-gated, mockable HTTP).
"""

from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.flags import feature_enabled
from app.integrations.ingest import classify_error
from app.job_sources.http_policy import jittered_backoff
from app.job_sources.keys import utc_now

HARVEST_FLAG = "greenhouse_harvest"
HARVEST_HOST = "harvest.greenhouse.io"
STATUS_MAP = {
    "active": "submitted",
    "in_process": "submitted",
    "hired": "succeeded",
    "rejected": "failed",
    "converted": "succeeded",
    "withdrawn": "failed",
}


class HarvestHttp(Protocol):
    def request(self, method: str, url: str, *, headers: dict[str, str]) -> tuple[int, dict[str, Any], dict[str, str]]: ...


class UrllibHarvestHttp:
    def request(self, method: str, url: str, *, headers: dict[str, str]) -> tuple[int, dict[str, Any], dict[str, str]]:
        req = Request(url, method=method, headers={"Accept": "application/json", "User-Agent": "AJAS-harvest/1.0", **headers})
        try:
            with urlopen(req, timeout=20) as resp:
                raw = resp.read()
                parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                hdrs = {k: v for k, v in resp.headers.items()}
                return int(getattr(resp, "status", 200)), parsed if isinstance(parsed, dict) else {"items": parsed}, hdrs
        except HTTPError as exc:
            raw = exc.read() if hasattr(exc, "read") else b""
            try:
                parsed = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            except Exception:
                parsed = {"error": raw.decode("utf-8", errors="replace")}
            if not isinstance(parsed, dict):
                parsed = {"error": parsed}
            hdrs = {k: v for k, v in (exc.headers.items() if exc.headers else [])}
            return int(exc.code), parsed, hdrs
        except URLError as exc:
            raise TimeoutError(str(exc.reason or exc)) from exc


def _auth_headers(api_key: str) -> dict[str, str]:
    import base64

    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def map_application(row: dict[str, Any]) -> dict[str, Any]:
    raw_status = str(row.get("status") or row.get("current_status") or "active").lower()
    mapped = STATUS_MAP.get(raw_status, "submitted")
    candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
    job = row.get("jobs")[0] if isinstance(row.get("jobs"), list) and row.get("jobs") else row.get("job") or {}
    if not isinstance(job, dict):
        job = {}
    emails = candidate.get("email_addresses")
    email = ""
    if isinstance(emails, list) and emails and isinstance(emails[0], dict):
        email = str(emails[0].get("value") or "")
    if not email:
        email = str(candidate.get("email") or row.get("email") or "")
    return {
        "id": str(row.get("id") or ""),
        "candidateId": str(row.get("candidate_id") or candidate.get("id") or ""),
        "candidateEmail": email,
        "jobId": str(job.get("id") or row.get("job_id") or ""),
        "jobTitle": str(job.get("name") or row.get("job_title") or ""),
        "status": mapped,
        "vendorStatus": raw_status,
        "appliedAt": str(row.get("applied_at") or row.get("created_at") or utc_now()),
        "updatedAt": str(row.get("last_activity") or row.get("updated_at") or utc_now()),
        "source": "greenhouse_harvest",
    }


def list_applications(
    *,
    api_key: str,
    email: str | None = None,
    page: int = 1,
    per_page: int = 50,
    http: HarvestHttp | None = None,
    pages: list[dict[str, Any]] | None = None,
    statuses: list[int] | None = None,
    base_url: str = "https://harvest.greenhouse.io/v1/applications",
) -> dict[str, Any]:
    if not feature_enabled(HARVEST_FLAG):
        return {"enabled": False, "items": [], "nextPage": None, "reason": "flag_off"}
    if not (api_key or "").strip() and pages is None:
        return {"enabled": True, "items": [], "nextPage": None, "reason": "not_configured"}

    # Fixture path: operator-supplied Harvest JSON (tests / local).
    if pages is not None:
        payload = pages[page - 1] if 0 <= page - 1 < len(pages) else {"applications": []}
        rows = payload.get("applications") if isinstance(payload, dict) else payload
        items = [map_application(row) for row in rows or [] if isinstance(row, dict)]
        if email:
            needle = email.lower()
            items = [row for row in items if needle in str(row.get("candidateEmail") or "").lower()]
        next_page = page + 1 if page < len(pages) else None
        return {"enabled": True, "items": items, "nextPage": next_page, "reason": "ok", "page": page}

    client = http or UrllibHarvestHttp()
    url = f"{base_url}?page={page}&per_page={per_page}"
    if email:
        url += f"&email={email}"
    attempt_statuses = list(statuses or [200])
    last_status = attempt_statuses[-1]
    for index, status in enumerate(attempt_statuses):
        info = classify_error(status)
        if info["retryable"] and index < len(attempt_statuses) - 1:
            _ = jittered_backoff(index, jitter=0.0)
            continue
        last_status = status
        break
    if last_status >= 400:
        return {"enabled": True, "items": [], "nextPage": None, "reason": classify_error(last_status)["class"], "status": last_status}

    status, payload, headers = client.request("GET", url, headers=_auth_headers(api_key))
    if status >= 400:
        return {"enabled": True, "items": [], "nextPage": None, "reason": classify_error(status)["class"], "status": status}
    if isinstance(payload, list):
        rows = payload
        next_flag = False
    else:
        rows = payload.get("applications") or payload.get("items") or payload.get("value") or []
        next_flag = bool(payload.get("next_page"))
    items = [map_application(row) for row in rows if isinstance(row, dict)]
    link = headers.get("Link") or headers.get("link") or ""
    next_page = page + 1 if 'rel="next"' in link or next_flag else None
    return {"enabled": True, "items": items, "nextPage": next_page, "reason": "ok", "page": page, "status": status}

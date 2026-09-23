"""Live LinkedIn job search + Easy Apply. Flag-gated; captcha never bypassed.

Guest job search uses LinkedIn's public jobs-guest endpoints (allowlisted HTTPS).
Easy Apply uses the operator's sealed session (li_at / JSESSIONID). Checkpoints
and CAPTCHAs return needs_manual. HTML scrape of logged-out walls is not a
captcha solver. SOURCE_TYPES stays {greenhouse, lever}.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener
from uuid import uuid4

from app.config import get_settings
from app.flags import feature_enabled
from app.integrations.linkedin_spec import detect_challenge
from app.job_sources.keys import utc_now
from app.job_sources.urls import GREENHOUSE_HOSTS, LEVER_HOSTS

LINKEDIN_FLAG = "linkedin_adapter"
EASY_APPLY_FLAG = "linkedin_easy_apply"
LINKEDIN_HOSTS = frozenset({"www.linkedin.com", "linkedin.com"})
GUEST_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
GUEST_JOB = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
VOYAGER_JOB = "https://www.linkedin.com/voyager/api/jobs/jobPostings/{job_id}"
_JOB_ID_RE = re.compile(r"(?:urn:li:jobPosting:|/jobs/view/)(\d+)", re.I)
_TITLE_RE = re.compile(r'class="[^"]*base-search-card__title[^"]*"[^>]*>([^<]+)', re.I)
_COMPANY_RE = re.compile(r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>\s*(?:<a[^>]*>)?([^<]+)', re.I)
_LOCATION_RE = re.compile(r'class="[^"]*job-search-card__location[^"]*"[^>]*>([^<]+)', re.I)
_TIME_RE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)
_HREF_RE = re.compile(r'href="(https://(?:www\.)?linkedin\.com/jobs/view/\d+[^"]*)"', re.I)

_HTTP: "LinkedInHttp | None" = None


class LinkedInHttp(Protocol):
    def get(self, url: str, *, headers: dict[str, str] | None = None) -> tuple[int, str | bytes | dict[str, Any], dict[str, str]]: ...

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, str | bytes | dict[str, Any], dict[str, str]]: ...


class UrllibLinkedInHttp:
    def get(self, url: str, *, headers: dict[str, str] | None = None) -> tuple[int, str | bytes | dict[str, Any], dict[str, str]]:
        return _urlopen("GET", url, headers=headers or {}, body=None)

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, str | bytes | dict[str, Any], dict[str, str]]:
        return _urlopen("POST", url, headers=headers or {}, body=body)


class MemoryLinkedInHttp:
    """In-process LinkedIn stand-in used by tests. Never opens sockets."""

    def __init__(self) -> None:
        self.gets: list[str] = []
        self.posts: list[str] = []
        self.get_handler: Any = None
        self.post_handler: Any = None
        self.guest_html: str = ""
        self.apply_status: int = 200
        self.apply_body: dict[str, Any] = {"id": "ea-test", "status": "APPLIED"}

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> tuple[int, str | bytes | dict[str, Any], dict[str, str]]:
        self.gets.append(url)
        if self.get_handler:
            return self.get_handler(url, headers or {})
        html = self.guest_html or "<html></html>"
        return 200, html, {"Content-Type": "text/html"}

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, str | bytes | dict[str, Any], dict[str, str]]:
        self.posts.append(url)
        if self.post_handler:
            return self.post_handler(url, headers or {}, body)
        return self.apply_status, dict(self.apply_body), {"Content-Type": "application/json"}


def set_linkedin_http(client: LinkedInHttp | None) -> None:
    global _HTTP
    _HTTP = client


def clear_linkedin_http() -> None:
    set_linkedin_http(None)


def _http() -> LinkedInHttp:
    return _HTTP or UrllibLinkedInHttp()


def _urlopen(method: str, url: str, *, headers: dict[str, str], body: dict[str, Any] | None) -> tuple[int, str | bytes | dict[str, Any], dict[str, str]]:
    _assert_allowlisted(url)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    merged = {"User-Agent": "AJAS-linkedin/1.0", "Accept": "text/html,application/json", **headers}
    if payload is not None:
        merged.setdefault("Content-Type", "application/json")
    request = Request(url, data=payload, method=method, headers=merged)

    class _NoRedirect:
        pass

    import urllib.request

    class Handler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):  # noqa: ANN001
            return None

    opener = build_opener(Handler)
    try:
        with opener.open(request, timeout=20) as resp:
            raw = resp.read()
            hdrs = {k: v for k, v in resp.headers.items()}
            return int(getattr(resp, "status", 200)), _decode_body(raw, hdrs), hdrs
    except HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        hdrs = {k: v for k, v in (exc.headers.items() if exc.headers else [])}
        return int(exc.code), _decode_body(raw, hdrs), hdrs
    except URLError as exc:
        raise TimeoutError(str(exc.reason or exc)) from exc


def _decode_body(raw: bytes, headers: dict[str, str]) -> str | dict[str, Any]:
    ctype = " ".join(headers.values()).lower() if headers else ""
    text = raw.decode("utf-8", errors="replace") if raw else ""
    if "json" in ctype or text.lstrip().startswith("{") or text.lstrip().startswith("["):
        try:
            parsed = json.loads(text or "{}")
            return parsed if isinstance(parsed, (dict, list)) else text
        except json.JSONDecodeError:
            return text
    return text


def allowed_hosts() -> frozenset[str]:
    settings = get_settings()
    raw = str(getattr(settings, "linkedin_allowed_hosts", "") or "").strip()
    if raw:
        return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())
    return LINKEDIN_HOSTS


def _assert_allowlisted(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in allowed_hosts():
        raise ValueError(f"linkedin host {host} is not allowlisted")


def live_search_allowed() -> bool:
    if not feature_enabled(LINKEDIN_FLAG):
        return False
    if _HTTP is not None:
        return True
    settings = get_settings()
    return bool(getattr(settings, "linkedin_live", False))


def live_connect_guard(*, apply: bool = False, account_id: str | None = None) -> dict[str, Any]:
    if apply and not feature_enabled(EASY_APPLY_FLAG) and not feature_enabled(LINKEDIN_FLAG):
        return {"ok": False, "reason": "flag_off", "bypass": False}
    if not apply and not feature_enabled(LINKEDIN_FLAG):
        return {"ok": False, "reason": "flag_off", "bypass": False}
    if not live_search_allowed():
        return {"ok": False, "reason": "live_disabled", "bypass": False}
    if apply:
        if not feature_enabled(EASY_APPLY_FLAG) and not feature_enabled(LINKEDIN_FLAG):
            return {"ok": False, "reason": "flag_off", "bypass": False}
        if account_id:
            from app.integrations.linkedin_session import STORE

            status = STORE.public(account_id).get("status")
            if status in {"expired", "revoked", "anonymous"}:
                return {"ok": False, "reason": "session_expired", "bypass": False}
        else:
            return {"ok": False, "reason": "needs_auth", "bypass": False}
    return {"ok": True, "reason": "ok", "bypass": False}


def parse_guest_html(html: str) -> list[dict[str, Any]]:
    text = html or ""
    jobs: list[dict[str, Any]] = []
    parts = re.split(r'data-entity-urn="urn:li:jobPosting:', text)
    for part in parts[1:]:
        job_id = part.split('"', 1)[0].strip()
        block = part[:4000]
        title_m = _TITLE_RE.search(block)
        company_m = _COMPANY_RE.search(block)
        loc_m = _LOCATION_RE.search(block)
        href_m = _HREF_RE.search(block)
        time_m = _TIME_RE.search(block)
        title = " ".join((title_m.group(1) if title_m else "").split())
        company = " ".join((company_m.group(1) if company_m else "").split())
        if not title or not company:
            continue
        url = (href_m.group(1) if href_m else f"https://www.linkedin.com/jobs/view/{job_id}").split("?")[0]
        easy = "easy apply" in block.lower()
        jobs.append(
            {
                "id": job_id,
                "jobId": job_id,
                "title": title,
                "company": company,
                "location": " ".join((loc_m.group(1) if loc_m else "").split()),
                "url": url,
                "apply_url": url,
                "postingUrl": url,
                "postedAt": time_m.group(1) if time_m else "",
                "easyApply": easy,
                "applyMethod": "easy_apply" if easy else "external",
            }
        )
    return jobs


def parse_voyager_json(payload: Any) -> list[dict[str, Any]]:
    rows: list[Any] = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("elements"), list):
            rows = payload["elements"]
        elif isinstance(payload.get("included"), list):
            rows = [item for item in payload["included"] if isinstance(item, dict) and "title" in item]
        elif isinstance(payload.get("jobs"), list):
            rows = payload["jobs"]
        elif payload.get("title"):
            rows = [payload]
    jobs: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        urn = str(item.get("entityUrn") or item.get("dashEntityUrn") or item.get("jobId") or item.get("id") or "")
        match = _JOB_ID_RE.search(urn) or _JOB_ID_RE.search(str(item.get("jobPostingId") or ""))
        job_id = match.group(1) if match else str(item.get("id") or "")
        company = item.get("companyDetails") or item.get("companyName") or item.get("company") or ""
        if isinstance(company, dict):
            company = company.get("name") or company.get("companyName") or ""
        title = item.get("title") or item.get("jobTitle") or ""
        if not title:
            continue
        url = str(item.get("jobPostingUrl") or item.get("applyUrl") or item.get("url") or "")
        if not url and job_id:
            url = f"https://www.linkedin.com/jobs/view/{job_id}"
        easy = bool(item.get("easyApply") or item.get("applyMethod") == "easy_apply")
        jobs.append(
            {
                "id": job_id or str(title),
                "title": title,
                "company": str(company or ""),
                "location": str(item.get("formattedLocation") or item.get("location") or ""),
                "description": str(item.get("description") or item.get("jobDescription") or ""),
                "url": url,
                "apply_url": url,
                "postedAt": str(item.get("listedAt") or item.get("postedAt") or ""),
                "easyApply": easy,
                "external_apply_url": str(item.get("externalApplyUrl") or item.get("companyApplyUrl") or ""),
            }
        )
    return jobs


def unwrap_linkedin_live(payload: Any) -> dict[str, Any]:
    if isinstance(payload, str) and ("base-search-card" in payload or "job-search-card" in payload or "urn:li:jobPosting:" in payload):
        return {"jobs": parse_guest_html(payload), "nextCursor": None}
    if isinstance(payload, dict) and not payload.get("jobs"):
        voyager = parse_voyager_json(payload)
        if voyager:
            return {**payload, "jobs": voyager}
    return payload if isinstance(payload, dict) else {"jobs": payload if isinstance(payload, list) else []}


def _session_headers(account_id: str | None) -> dict[str, str]:
    if not account_id:
        return {}
    from app.integrations.linkedin_session import STORE

    token = STORE.unlock(account_id)
    cookies = token.strip()
    headers = {"Cookie": cookies if "li_at=" in cookies else f"li_at={cookies}"}
    csrf = ""
    for part in cookies.replace(";", " ").split():
        if part.lower().startswith("jsessionid="):
            csrf = part.split("=", 1)[1].strip().strip('"')
    if csrf:
        headers["csrf-token"] = csrf
        headers["Csrf-Token"] = csrf
    headers["x-restli-protocol-version"] = "2.0.0"
    return headers


def _challenge_from(status: int, body: Any) -> dict[str, Any] | None:
    row = detect_challenge(body, status=status)
    if row["kind"] in {"captcha", "challenge"}:
        return row
    if status in {401, 403}:
        return {
            "kind": "challenge" if status == 403 else "session",
            "code": "CHALLENGE" if status == 403 else "SESSION_EXPIRED",
            "userPrompt": "Reconnect the LinkedIn account, then retry.",
            "bypass": False,
        }
    return None


def search_url(spec: Any, *, start: int = 0) -> str:
    keywords = str(getattr(spec, "keywords", None) or (spec.get("keywords") if isinstance(spec, dict) else "") or "")
    locations = getattr(spec, "locations", None)
    if locations is None and isinstance(spec, dict):
        locations = spec.get("locations") or spec.get("location")
    location = ""
    if isinstance(locations, (list, tuple)) and locations:
        location = str(locations[0])
    elif isinstance(locations, str):
        location = locations
    workplace = str(getattr(spec, "workplace", None) or (spec.get("workplace") if isinstance(spec, dict) else "") or "")
    params: dict[str, str | int] = {"start": int(start), "keywords": keywords}
    if location:
        params["location"] = location
    if workplace == "remote":
        params["f_WT"] = 2
    params["f_AL"] = "true"
    return f"{GUEST_SEARCH}?{urlencode(params)}"


def search_jobs(
    spec: Any,
    *,
    live: bool = False,
    account_id: str | None = None,
    start: int = 0,
) -> dict[str, Any]:
    if not live:
        return {"jobs": [], "reason": "fixture", "liveFetch": False, "bypass": False}
    gate = live_connect_guard(apply=False)
    if not gate["ok"]:
        return {"jobs": [], "reason": gate["reason"], "liveFetch": False, "bypass": False}
    url = search_url(spec, start=start)
    status, body, _headers = _http().get(url, headers=_session_headers(account_id) if account_id else {})
    challenge = _challenge_from(status, body)
    if challenge:
        return {
            "jobs": [],
            "reason": "needs_manual" if challenge.get("kind") in {"captcha", "challenge"} else "session_expired",
            "code": challenge.get("code"),
            "userPrompt": challenge.get("userPrompt"),
            "hitl": True,
            "bypass": False,
            "liveFetch": True,
        }
    jobs: list[dict[str, Any]]
    if isinstance(body, dict):
        jobs = parse_voyager_json(body)
    else:
        jobs = parse_guest_html(str(body))
    return {
        "jobs": jobs,
        "reason": "ok",
        "liveFetch": True,
        "cursor": str(start),
        "nextCursor": str(start + len(jobs)) if jobs else None,
        "bypass": False,
    }


def _external_vendor(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if host in GREENHOUSE_HOSTS or host.endswith(".greenhouse.io"):
        return "greenhouse"
    if host in LEVER_HOSTS or host.endswith(".lever.co"):
        return "lever"
    return None


def deliver_application(
    job: dict[str, Any],
    fields: dict[str, Any],
    attachments: list[dict[str, Any]],
    answers: dict[str, str],
    *,
    account_id: str | None = None,
    live: bool = False,
) -> dict[str, Any]:
    """POST Easy Apply or route LinkedIn-hosted jobs to Greenhouse/Lever apply URLs."""
    if not live:
        return {"status": "submitted", "reason": "ok", "liveFetch": False, "bypass": False}
    posting = str(job.get("postingUrl") or job.get("applyUrl") or job.get("url") or "")
    external = str(job.get("externalApplyUrl") or "")
    vendor = _external_vendor(external or posting)
    if vendor:
        from app.auto_apply.models import AutoApplyAttempt
        from app.auto_apply.submitters import submit_to_vendor
        from app.config import get_settings as _settings

        settings = _settings()
        attempt = AutoApplyAttempt(
            user_id="linkedin",
            job_id=str(job.get("id") or ""),
            posting_url=external or posting,
            vendor=vendor,  # type: ignore[arg-type]
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        api_key = settings.greenhouse_submit_api_key if vendor == "greenhouse" else settings.lever_submit_api_key
        outcome = submit_to_vendor(attempt, fields, live=bool(settings.auto_apply_live_submit), api_key=api_key)
        status = "submitted" if outcome.status in {"succeeded", "submitted"} else outcome.status
        if status == "succeeded":
            status = "submitted"
        return {
            "status": status,
            "reason": outcome.error_code or outcome.status,
            "vendor": vendor,
            "endpoint": outcome.endpoint,
            "liveFetch": bool(settings.auto_apply_live_submit),
            "bypass": False,
        }
    gate = live_connect_guard(apply=True, account_id=account_id)
    if not gate["ok"]:
        return {"status": "needs_manual" if gate["reason"] == "session_expired" else gate["reason"], "reason": gate["reason"], "bypass": False, "liveFetch": False}
    job_id = str(job.get("sourcePostingId") or job.get("id") or "")
    match = _JOB_ID_RE.search(job_id) or _JOB_ID_RE.search(posting)
    if match:
        job_id = match.group(1)
    if not job_id:
        return {"status": "failed", "reason": "missing_job_id", "bypass": False, "liveFetch": False}
    headers = _session_headers(account_id)
    apply_url = f"{VOYAGER_JOB.format(job_id=job_id)}?action=apply"
    body = {
        "followCompany": False,
        "referenceId": str(uuid4()),
        "trackingCode": "ajas_easy_apply",
        "questionAnswers": [{"question": key, "answer": value} for key, value in answers.items()],
        "profile": {k: v for k, v in fields.items() if k not in {"resume", "coverLetter"}},
        "attachmentNames": [item.get("name") for item in attachments if item.get("name")],
    }
    status, resp, _hdrs = _http().post(apply_url, headers=headers, body=body)
    challenge = _challenge_from(status, resp)
    if challenge:
        kind = "needs_manual"
        reason = "captcha" if challenge.get("kind") == "captcha" else ("session_expired" if challenge.get("code") == "SESSION_EXPIRED" else "challenge")
        return {
            "status": kind,
            "reason": reason,
            "code": challenge.get("code"),
            "userPrompt": challenge.get("userPrompt"),
            "hitl": True,
            "abort": True,
            "bypass": False,
            "liveFetch": True,
        }
    if status >= 400:
        return {"status": "failed", "reason": f"http_{status}", "liveFetch": True, "bypass": False}
    confirmation = ""
    if isinstance(resp, dict):
        confirmation = str(resp.get("id") or resp.get("applicationId") or resp.get("status") or "")
    return {
        "status": "submitted",
        "reason": "ok",
        "confirmation": confirmation or f"EA-{uuid4().hex[:10].upper()}",
        "liveFetch": True,
        "bypass": False,
    }

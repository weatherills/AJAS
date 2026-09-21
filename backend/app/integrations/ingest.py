"""Indeed / LinkedIn fixture ingestion: fetch, normalize, dedupe, apply-method, throttle."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from app.auto_apply.captcha import detect as detect_captcha
from app.flags import feature_enabled
from app.integrations.search import SearchSpec, matches_search, parse_search
from app.job_sources.boards import SOURCE_FLAGS, backoff_seconds, iter_pages
from app.job_sources.circuit import allow as circuit_allow, record_status
from app.job_sources.enrich import enrich_posting, parse_salary
from app.job_sources.http_policy import jittered_backoff
from app.job_sources.keys import canonical_id_for, canonical_key, content_hash, dedupe_namespace, utc_now
from app.job_sources.robots import can_fetch

EASY_APPLY_MARKERS = (
    "easy_apply",
    "easyapply",
    "easy-apply",
    "linkedin_easy_apply",
    "easy apply",
)


class RateLimiter:
    """Per-source token bucket used by extra-board ingest and Easy Apply."""

    def __init__(self) -> None:
        self._used: dict[str, int] = {}

    def reset(self) -> None:
        self._used.clear()

    def allow(self, source: str, *, cost: int = 1, cap: int = 20) -> dict[str, Any]:
        used = self._used.get(source, 0)
        if used + cost > cap:
            return {"allowed": False, "reason": "cap", "used": used, "cap": cap, "source": source}
        self._used[source] = used + cost
        return {"allowed": True, "reason": "ok", "used": used + cost, "cap": cap, "source": source}


LIMITER = RateLimiter()


def reset_limiter() -> None:
    LIMITER.reset()


def throttle(source: str, *, cost: int = 1, cap: int = 20, jitter: float = 0.0) -> dict[str, Any]:
    row = LIMITER.allow(source, cost=cost, cap=cap)
    delay = 0.0
    if row["allowed"] and jitter > 0:
        delay = random.uniform(0.05, jitter)
    row["delaySeconds"] = round(delay, 4)
    row["backoffSeconds"] = backoff_seconds(max(0, int(row["used"]) - 1))
    return row


def classify_error(status: int | None, payload: Any = None) -> dict[str, Any]:
    captcha = detect_captcha(payload)
    if captcha["captcha"]:
        return {"class": "captcha", "retryable": False, "action": "needs_manual", "bypass": False}
    code = int(status or 0)
    if code == 429:
        return {"class": "rate_limited", "retryable": True, "action": "backoff"}
    if code in {408, 503, 504} or code >= 500:
        return {"class": "transient", "retryable": True, "action": "retry"}
    if 400 <= code < 500:
        return {"class": "permanent", "retryable": False, "action": "fail"}
    return {"class": "ok", "retryable": False, "action": "continue"}


def retry_with_backoff(
    statuses: list[int],
    *,
    max_attempts: int = 4,
    sleeper=None,
    jitter: float = 0.0,
) -> dict[str, Any]:
    """Walk a sequence of HTTP statuses (tests inject the sequence)."""
    attempts: list[dict[str, Any]] = []
    final = classify_error(statuses[-1] if statuses else 500)
    for index, status in enumerate(statuses[:max_attempts]):
        info = classify_error(status)
        delay = jittered_backoff(index, jitter=jitter) if info["retryable"] else 0.0
        attempts.append({"status": status, **info, "delaySeconds": delay})
        if sleeper and delay:
            sleeper(delay)
        if not info["retryable"]:
            final = info
            break
        final = info
    return {"attempts": attempts, "final": final, "retried": len(attempts) > 1}


def detect_apply_method(job: dict[str, Any]) -> dict[str, str]:
    raw = " ".join(
        str(job.get(key) or "")
        for key in ("apply_method", "applyMethod", "application_type", "applyType", "apply_type", "apply")
    ).lower()
    url = str(job.get("apply_url") or job.get("url") or job.get("postingUrl") or "").lower()
    easy = bool(job.get("easyApply") or job.get("easy_apply"))
    if not easy:
        easy = any(marker in raw for marker in EASY_APPLY_MARKERS)
    source = str(job.get("source") or job.get("source_type") or "").lower()
    if not easy and (source == "linkedin" or "linkedin.com" in url):
        easy = not str(job.get("external_apply_url") or "")
    method = "easy_apply" if easy else "external"
    return {
        "applyMethod": method,
        "applyUrl": str(job.get("apply_url") or job.get("url") or job.get("external_apply_url") or ""),
        "externalApplyUrl": str(job.get("external_apply_url") or ("" if easy else (job.get("apply_url") or job.get("url") or ""))),
    }


def _first(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("name") or value.get("text") or value.get("label")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return ""


def normalize_job(source: str, job: dict[str, Any]) -> dict[str, Any]:
    title = _first(job.get("title"), job.get("jobTitle"))
    company = _first(job.get("company"), job.get("companyName"), job.get("employer"))
    location = _first(job.get("location"), job.get("jobLocation"))
    if isinstance(job.get("location"), dict):
        location = _first(job["location"].get("display"), job["location"].get("name"), location)
    body = _first(job.get("description"), job.get("body"), job.get("content"))
    apply_url = _first(job.get("apply_url"), job.get("url"), job.get("postingUrl"), job.get("link"))
    employment = _first(job.get("employment_type"), job.get("type"), job.get("jobType"))
    extra = enrich_posting(title=title, company=company, location=location, body=body)
    salary = parse_salary(body)
    apply = detect_apply_method({**job, "apply_url": apply_url, "url": apply_url, "source": source})
    namespace = dedupe_namespace(company=company, apply_url=apply_url)
    key = canonical_key(title=title, location=extra.get("location") or location, namespace=namespace)
    digest = content_hash(
        title=title,
        company=company,
        location=str(extra.get("location") or location),
        employment_type=employment,
        apply_url=apply_url,
        description_text=str(extra.get("description") or body),
    )
    posting_id = str(job.get("id") or job.get("source_posting_id") or canonical_id_for(key)[:12])
    return {
        "id": canonical_id_for(f"{source}:{posting_id}:{digest[:12]}"),
        "source": source,
        "sourcePostingId": posting_id,
        "title": title,
        "company": company,
        "location": extra.get("location") or location,
        "workplace": extra.get("workplace"),
        "seniority": extra.get("seniority"),
        "seniorityLevel": extra.get("seniorityLevel"),
        "salaryMin": extra.get("salaryMin") if extra.get("salaryMin") is not None else salary["min"],
        "salaryMax": extra.get("salaryMax") if extra.get("salaryMax") is not None else salary["max"],
        "employmentType": employment,
        "description": extra.get("description") or body,
        "postingUrl": apply_url,
        "applyUrl": apply["applyUrl"],
        "applyMethod": apply["applyMethod"],
        "externalApplyUrl": apply["externalApplyUrl"],
        "canonicalKey": key,
        "contentHash": digest,
        "page": int(job.get("page") or 1),
        "sourceMetadata": {
            "source": source,
            "rawId": posting_id,
            "fetchedAt": utc_now(),
        },
    }


def _pages_from(payload: Any) -> list[list[Any]]:
    return iter_pages(payload)


def _flag_for(source: str) -> str | None:
    return SOURCE_FLAGS.get(source)


def ingest_jobs(
    source: str,
    payload: Any,
    *,
    listing_url: str | None = None,
    search: SearchSpec | dict[str, Any] | None = None,
    seen: dict[str, dict[str, Any]] | None = None,
    store: dict[str, dict[str, Any]] | None = None,
    rate_cap: int = 50,
) -> dict[str, Any]:
    """Normalize fixture pages into canonical postings with idempotent upserts.

    Live HTML scraping of Indeed/LinkedIn is not implemented. When ``listing_url``
    is supplied, robots + consent must pass; fixture hosts are used in tests.
    """
    spec = search if isinstance(search, SearchSpec) else parse_search(search)
    flag = _flag_for(source)
    metrics = {
        "source": source,
        "ingested": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "pages": 0,
        "enabled": bool(flag and feature_enabled(flag)),
    }
    if not flag or not feature_enabled(flag):
        return {"jobs": [], "metrics": metrics, "search": spec.as_dict(), "reason": "flag_off"}
    if not circuit_allow(source):
        metrics["failed"] += 1
        return {"jobs": [], "metrics": metrics, "search": spec.as_dict(), "reason": "circuit_open"}
    if listing_url and not can_fetch(listing_url):
        metrics["failed"] += 1
        return {"jobs": [], "metrics": metrics, "search": spec.as_dict(), "reason": "robots_or_consent"}

    bucket = store if store is not None else {}
    known = seen if seen is not None else {}
    out: list[dict[str, Any]] = []
    pages = _pages_from(payload)
    for index, rows in enumerate(pages, start=1):
        metrics["pages"] += 1
        _ = backoff_seconds(index - 1)
        gate = throttle(source, cap=rate_cap, jitter=0.0)
        if not gate["allowed"]:
            metrics["skipped"] += max(0, len(rows) if isinstance(rows, list) else 0)
            record_status(source, 429)
            break
        if not isinstance(rows, list):
            continue
        for job in rows:
            if not isinstance(job, dict):
                metrics["failed"] += 1
                continue
            try:
                row = normalize_job(source, {**job, "page": job.get("page") or index})
            except Exception:
                metrics["failed"] += 1
                continue
            if not row["title"] or not row["company"] or not row["postingUrl"]:
                metrics["failed"] += 1
                continue
            if not matches_search(row, spec):
                metrics["skipped"] += 1
                continue
            fingerprint = f"{row['contentHash']}|{row['postingUrl']}"
            previous = known.get(fingerprint) or bucket.get(row["id"])
            if previous and previous.get("contentHash") == row["contentHash"]:
                metrics["skipped"] += 1
                out.append(previous)
                continue
            if previous:
                metrics["updated"] += 1
            else:
                metrics["ingested"] += 1
            known[fingerprint] = row
            bucket[row["id"]] = row
            out.append(row)
            if len(out) >= spec.limit:
                break
        if len(out) >= spec.limit:
            break
    record_status(source, 200)
    return {
        "jobs": out[: spec.limit],
        "metrics": metrics,
        "search": spec.as_dict(),
        "reason": "ok",
    }


def indeed_ingest(payload: Any, **kwargs: Any) -> dict[str, Any]:
    return ingest_jobs("indeed", payload, **kwargs)


def linkedin_ingest(payload: Any, **kwargs: Any) -> dict[str, Any]:
    return ingest_jobs("linkedin", payload, **kwargs)


def listing_fetcher(source: str, payload: Any, **kwargs: Any) -> dict[str, Any]:
    """Paginated listing fetch used by Indeed and LinkedIn Jobs."""
    return ingest_jobs(source, payload, **kwargs)


def stable_job_id(source: str, posting_id: str, digest: str) -> str:
    raw = f"{source}:{posting_id}:{digest}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()

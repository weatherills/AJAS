"""Indeed / LinkedIn / Glassdoor / Workday / ZipRecruiter / Hired / Wellfound fixture ingestion."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from app.auto_apply.captcha import detect as detect_captcha
from app.flags import feature_enabled
from app.integrations import linkedin_audit
from app.integrations.glassdoor_spec import RATE_PLAN as GLASSDOOR_RATE, map_glassdoor_job, unwrap_glassdoor_payload
from app.integrations.hired_spec import RATE_PLAN as HIRED_RATE, map_hired_job, unwrap_hired_payload
from app.integrations.indeed_spec import RATE_PLAN as INDEED_RATE, map_indeed_job, unwrap_indeed_payload
from app.integrations.linkedin_spec import (
    RATE_PLAN,
    bump,
    detect_challenge,
    listing_dedupe_key,
    listing_visibility,
    map_linkedin_job,
    walk_pages,
)
from app.integrations.linkedin_client import unwrap_linkedin_live
from app.integrations.wellfound_spec import RATE_PLAN as WELLFOUND_RATE, map_wellfound_job, unwrap_wellfound_payload
from app.integrations.workday_spec import RATE_PLAN as WORKDAY_RATE, map_workday_job, unwrap_workday_payload
from app.integrations.ziprecruiter_spec import RATE_PLAN as ZIP_RATE, map_ziprecruiter_job, unwrap_ziprecruiter_payload
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
    from app.integrations.linkedin_spec import reset_counters

    LIMITER.reset()
    reset_counters()


def throttle(source: str, *, cost: int = 1, cap: int = 20, jitter: float = 0.0) -> dict[str, Any]:
    row = LIMITER.allow(source, cost=cost, cap=cap)
    delay = 0.0
    if row["allowed"] and jitter > 0:
        delay = random.uniform(0.05, jitter)
    row["delaySeconds"] = round(delay, 4)
    row["backoffSeconds"] = backoff_seconds(max(0, int(row["used"]) - 1))
    if not row["allowed"]:
        bump("rate_limited")
    return row


def classify_error(status: int | None, payload: Any = None) -> dict[str, Any]:
    challenge = detect_challenge(payload, status=status)
    if challenge["kind"] == "captcha":
        bump("captcha")
        return {
            "class": "captcha",
            "retryable": False,
            "action": "needs_manual",
            "bypass": False,
            "userPrompt": challenge["userPrompt"],
        }
    if challenge["kind"] == "challenge":
        return {
            "class": "challenge",
            "retryable": False,
            "action": "needs_manual",
            "bypass": False,
            "userPrompt": challenge["userPrompt"],
        }
    if challenge["kind"] == "timeout":
        bump("timeout")
        return {
            "class": "timeout",
            "retryable": True,
            "action": "retry",
            "bypass": False,
            "userPrompt": challenge["userPrompt"],
        }
    captcha = detect_captcha(payload)
    if captcha["captcha"]:
        bump("captcha")
        return {"class": "captcha", "retryable": False, "action": "needs_manual", "bypass": False}
    code = int(status or 0)
    if code == 429:
        bump("rate_limited")
        return {"class": "rate_limited", "retryable": True, "action": "backoff"}
    if code in {408, 503, 504} or code >= 500:
        bump("transient")
        return {"class": "transient", "retryable": True, "action": "retry"}
    if 400 <= code < 500:
        bump("permanent")
        return {"class": "permanent", "retryable": False, "action": "fail"}
    return {"class": "ok", "retryable": False, "action": "continue"}


def retry_with_backoff(
    statuses: list[int],
    *,
    max_attempts: int = 4,
    sleeper=None,
    jitter: float = 0.0,
    payload: Any = None,
) -> dict[str, Any]:
    """Walk a sequence of HTTP statuses (tests inject the sequence)."""
    attempts: list[dict[str, Any]] = []
    final = classify_error(statuses[-1] if statuses else 500, payload)
    for index, status in enumerate(statuses[:max_attempts]):
        info = classify_error(status, payload)
        delay = jittered_backoff(index, jitter=jitter) if info["retryable"] else 0.0
        attempts.append({"status": status, **info, "delaySeconds": delay})
        if info["retryable"]:
            bump("retries")
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


MAPPERS = {
    "linkedin": map_linkedin_job,
    "indeed": map_indeed_job,
    "glassdoor": map_glassdoor_job,
    "workday": map_workday_job,
    "ziprecruiter": map_ziprecruiter_job,
    "hired": map_hired_job,
    "wellfound": map_wellfound_job,
}

UNWRAPPERS = {
    "linkedin": unwrap_linkedin_live,
    "indeed": unwrap_indeed_payload,
    "glassdoor": unwrap_glassdoor_payload,
    "workday": unwrap_workday_payload,
    "ziprecruiter": unwrap_ziprecruiter_payload,
    "hired": unwrap_hired_payload,
    "wellfound": unwrap_wellfound_payload,
}

INGEST_CAPS = {
    "linkedin": int(RATE_PLAN["ingest"]["capPerWindow"]),
    "indeed": int(INDEED_RATE["ingest"]["capPerWindow"]),
    "glassdoor": int(GLASSDOOR_RATE["ingest"]["capPerWindow"]),
    "workday": int(WORKDAY_RATE["ingest"]["capPerWindow"]),
    "ziprecruiter": int(ZIP_RATE["ingest"]["capPerWindow"]),
    "hired": int(HIRED_RATE["ingest"]["capPerWindow"]),
    "wellfound": int(WELLFOUND_RATE["ingest"]["capPerWindow"]),
}

HTTP_INGEST_SOURCES = frozenset(MAPPERS)


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
    mapper = MAPPERS.get(source)
    mapped = mapper(job) if mapper else None
    if mapped:
        title = str(mapped.get("title") or "")
        company = str(mapped.get("company") or "")
        location = str(mapped.get("location") or "")
        body = str(mapped.get("description") or "")
        apply_url = str(mapped.get("postingUrl") or "")
        employment = str(mapped.get("employmentType") or "")
        posted_at = str(mapped.get("postedAt") or "")
        posting_id = str(mapped.get("sourcePostingId") or "")
        listing_key = str(mapped.get("listingKey") or "")
        visibility = str(mapped.get("visibility") or "public")
        visible = bool(mapped.get("visible"))
    else:
        title = _first(job.get("title"), job.get("jobTitle"))
        company = _first(job.get("company"), job.get("companyName"), job.get("employer"))
        location = _first(job.get("location"), job.get("jobLocation"))
        if isinstance(job.get("location"), dict):
            location = _first(job["location"].get("display"), job["location"].get("name"), location)
        body = _first(job.get("description"), job.get("body"), job.get("content"))
        apply_url = _first(job.get("apply_url"), job.get("url"), job.get("postingUrl"), job.get("link"))
        employment = _first(job.get("employment_type"), job.get("type"), job.get("jobType"))
        posted_at = _first(job.get("postedAt"), job.get("posted_at"), job.get("listedAt"), job.get("datePosted"))
        vis = listing_visibility(job)
        visibility = vis["reason"]
        visible = vis["visible"]
        listing_key = listing_dedupe_key(title=title, company=company, location=location, posted_at=posted_at)
        posting_id = str(job.get("id") or job.get("source_posting_id") or canonical_id_for(listing_key)[:12])
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
        "postedAt": posted_at,
        "listingKey": listing_key,
        "visibility": visibility,
        "visible": visible,
        "canonicalKey": key,
        "contentHash": digest,
        "page": int(job.get("page") or 1),
        "sourceMetadata": {
            "source": source,
            "rawId": posting_id,
            "fetchedAt": utc_now(),
            "postedAt": posted_at,
        },
    }


def _pages_from(payload: Any) -> list[list[Any]]:
    return iter_pages(payload)


def _board_pages(source: str, payload: Any) -> tuple[list[list[Any]], dict[str, Any]]:
    unwrap = UNWRAPPERS.get(source)
    if unwrap:
        payload = unwrap(payload)
    walked = walk_pages(payload)
    return [list(page.get("jobs") or []) for page in walked["pages"]], {
        "stop": walked["stop"],
        "cursors": walked["cursors"],
        "windowSize": walked["windowSize"],
        "mode": "cursor",
    }


def _flag_for(source: str) -> str | None:
    return SOURCE_FLAGS.get(source)


def _auth_blocked(source: str, payload: Any, html: str | None = None) -> str | None:
    """Hired/Wellfound require a token. Hired CAPTCHA never bypasses."""
    if source == "hired":
        from app.job_sources.hired import auth_gate

        gate = auth_gate(html if html is not None else payload)
        if gate.action != "continue":
            if gate.action == "needs_manual":
                bump("captcha")
            return gate.action
    elif source == "wellfound":
        from app.job_sources.wellfound_auth import require_auth

        if not require_auth():
            return "needs_auth"
    return None


def ingest_jobs(
    source: str,
    payload: Any,
    *,
    listing_url: str | None = None,
    search: SearchSpec | dict[str, Any] | None = None,
    seen: dict[str, dict[str, Any]] | None = None,
    store: dict[str, dict[str, Any]] | None = None,
    rate_cap: int | None = None,
    html: str | None = None,
) -> dict[str, Any]:
    """Normalize fixture pages into canonical postings with idempotent upserts.

    Live HTML scraping of extra boards is not implemented. When ``listing_url``
    is supplied, robots + consent must pass; fixture hosts are used in tests.
    """
    spec = search if isinstance(search, SearchSpec) else parse_search(search)
    flag = _flag_for(source)
    cap = int(rate_cap if rate_cap is not None else INGEST_CAPS.get(source, 50))
    mapped_source = source in MAPPERS
    metrics = {
        "source": source,
        "ingested": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "pages": 0,
        "enabled": bool(flag and feature_enabled(flag)),
        "privateSkipped": 0,
        "expiredSkipped": 0,
        "deduped": 0,
    }
    pagination = {"stop": "ok", "cursors": [], "windowSize": 25, "mode": "offset"}
    if not flag or not feature_enabled(flag):
        return {"jobs": [], "metrics": metrics, "search": spec.as_dict(), "reason": "flag_off", "pagination": pagination}
    if not circuit_allow(source):
        metrics["failed"] += 1
        bump("circuit_open")
        linkedin_audit.record("circuit_open", reason="circuit_open", source=source)
        return {"jobs": [], "metrics": metrics, "search": spec.as_dict(), "reason": "circuit_open", "pagination": pagination}
    if listing_url and not can_fetch(listing_url):
        metrics["failed"] += 1
        return {"jobs": [], "metrics": metrics, "search": spec.as_dict(), "reason": "robots_or_consent", "pagination": pagination}
    blocked = _auth_blocked(source, payload, html)
    if blocked:
        metrics["failed"] += 1
        return {"jobs": [], "metrics": metrics, "search": spec.as_dict(), "reason": blocked, "pagination": pagination}

    bucket = store if store is not None else {}
    known = seen if seen is not None else {}
    out: list[dict[str, Any]] = []
    if mapped_source:
        pages, pagination = _board_pages(source, payload)
    else:
        pages = _pages_from(payload)
        pagination = {"stop": "no_next_cursor", "cursors": [], "windowSize": 25, "mode": "offset"}
    for index, rows in enumerate(pages, start=1):
        metrics["pages"] += 1
        _ = backoff_seconds(index - 1)
        bump("requests")
        gate = throttle(source, cap=cap, jitter=0.0)
        if not gate["allowed"]:
            metrics["skipped"] += max(0, len(rows) if isinstance(rows, list) else 0)
            record_status(source, 429)
            pagination["stop"] = "rate_cap"
            linkedin_audit.record("rate_limited", source=source, used=gate["used"], cap=gate["cap"])
            break
        if not isinstance(rows, list):
            continue
        linkedin_audit.record("fetch_page", source=source, page=index, count=len(rows))
        for job in rows:
            if not isinstance(job, dict):
                metrics["failed"] += 1
                continue
            try:
                row = normalize_job(source, {**job, "page": job.get("page") or index})
            except Exception:
                metrics["failed"] += 1
                continue
            if mapped_source and not row.get("visible", True):
                metrics["skipped"] += 1
                if row.get("visibility") == "private":
                    metrics["privateSkipped"] += 1
                    bump("private_skipped")
                    linkedin_audit.record("skipped_private", source=source, listingKey=row.get("listingKey"))
                else:
                    metrics["expiredSkipped"] += 1
                    bump("expired_skipped")
                    linkedin_audit.record("skipped_expired", source=source, listingKey=row.get("listingKey"))
                continue
            if not row["title"] or not row["company"] or not row["postingUrl"]:
                metrics["failed"] += 1
                continue
            if not matches_search(row, spec):
                metrics["skipped"] += 1
                continue
            fingerprint = f"{row['contentHash']}|{row['postingUrl']}"
            listing_key = str(row.get("listingKey") or "")
            posted_at = str(row.get("postedAt") or "")
            previous = None
            if mapped_source and listing_key and posted_at:
                previous = known.get(listing_key)
            if previous is None:
                previous = known.get(fingerprint) or bucket.get(row["id"])
            listing_hit = bool(
                mapped_source and listing_key and posted_at and previous and previous.get("listingKey") == listing_key
            )
            if previous and (listing_hit or previous.get("contentHash") == row["contentHash"]):
                metrics["skipped"] += 1
                metrics["deduped"] += 1
                bump("deduped")
                linkedin_audit.record("deduped", source=source, listingKey=listing_key)
                if not any(item.get("id") == previous.get("id") for item in out):
                    out.append(previous)
                continue
            if previous:
                metrics["updated"] += 1
            else:
                metrics["ingested"] += 1
            known[fingerprint] = row
            if listing_key and posted_at:
                known[listing_key] = row
            bucket[row["id"]] = row
            out.append(row)
            if len(out) >= spec.limit:
                pagination["stop"] = "limit_reached"
                break
        if len(out) >= spec.limit:
            pagination["stop"] = "limit_reached"
            break
    record_status(source, 200)
    linkedin_audit.record(
        "fetch",
        source=source,
        ingested=metrics["ingested"],
        skipped=metrics["skipped"],
        failed=metrics["failed"],
        pages=metrics["pages"],
        stop=pagination.get("stop"),
    )
    return {
        "jobs": out[: spec.limit],
        "metrics": metrics,
        "search": spec.as_dict(),
        "reason": "ok",
        "pagination": pagination,
    }


def indeed_ingest(payload: Any, **kwargs: Any) -> dict[str, Any]:
    return ingest_jobs("indeed", payload, **kwargs)


def linkedin_ingest(payload: Any, **kwargs: Any) -> dict[str, Any]:
    live = bool(kwargs.pop("live", False))
    account_id = kwargs.pop("account_id", None)
    empty = payload is None or payload == {} or (isinstance(payload, dict) and not payload.get("jobs") and not payload.get("pages"))
    if live and empty:
        from app.integrations.linkedin_client import search_jobs
        from app.integrations.search import parse_search

        spec = kwargs.get("search")
        fetched = search_jobs(spec if spec is not None else parse_search(spec), live=True, account_id=account_id)
        if fetched.get("reason") != "ok":
            return {
                "jobs": [],
                "metrics": {"source": "linkedin", "ingested": 0, "enabled": True, "liveFetch": fetched.get("liveFetch")},
                "search": parse_search(spec).as_dict() if not hasattr(spec, "as_dict") else spec.as_dict(),
                "reason": fetched.get("reason"),
                "liveFetch": fetched.get("liveFetch"),
                "bypass": False,
                "userPrompt": fetched.get("userPrompt"),
                "pagination": {"stop": fetched.get("reason"), "cursors": [], "windowSize": 25, "mode": "cursor"},
            }
        payload = {"jobs": fetched.get("jobs") or [], "nextCursor": fetched.get("nextCursor")}
        result = ingest_jobs("linkedin", payload, **kwargs)
        result["liveFetch"] = True
        result["reason"] = result.get("reason") or "ok"
        return result
    result = ingest_jobs("linkedin", payload, **kwargs)
    result.setdefault("liveFetch", False)
    return result


def glassdoor_ingest(payload: Any, **kwargs: Any) -> dict[str, Any]:
    return ingest_jobs("glassdoor", payload, **kwargs)


def workday_ingest(payload: Any, **kwargs: Any) -> dict[str, Any]:
    return ingest_jobs("workday", payload, **kwargs)


def ziprecruiter_ingest(payload: Any, **kwargs: Any) -> dict[str, Any]:
    return ingest_jobs("ziprecruiter", payload, **kwargs)


def hired_ingest(payload: Any, **kwargs: Any) -> dict[str, Any]:
    return ingest_jobs("hired", payload, **kwargs)


def wellfound_ingest(payload: Any, **kwargs: Any) -> dict[str, Any]:
    return ingest_jobs("wellfound", payload, **kwargs)


def listing_fetcher(source: str, payload: Any, **kwargs: Any) -> dict[str, Any]:
    """Paginated listing fetch used by extra-board ingest connectors."""
    return ingest_jobs(source, payload, **kwargs)


def stable_job_id(source: str, posting_id: str, digest: str) -> str:
    raw = f"{source}:{posting_id}:{digest}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()

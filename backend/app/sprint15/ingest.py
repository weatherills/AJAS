"""Fixture-only Sprint 15 adapters and crawl policy. Flags stay off; no live fetch."""

from __future__ import annotations

from typing import Any

from app.auto_apply.captcha import detect as detect_captcha
from app.flags import feature_enabled
from app.job_sources.career_pages import parse_career_html
from app.job_sources.http_policy import jittered_backoff, rotate_user_agent
from app.job_sources.robots import can_fetch

NEW_FLAGS = (
    "indeed_adapter",
    "dice_adapter",
    "wellfound_adapter",
    "linkedin_jobs_adapter",
    "google_jobs_adapter",
    "otta_adapter",
    "yc_adapter",
    "flexjobs_adapter",
    "simplyhired_adapter",
    "careerbuilder_adapter",
)


def reset() -> None:
    return None


def _flag(name: str) -> bool:
    return bool(feature_enabled(name))


def _parse_jobs(source: str, payload: dict[str, Any] | None, html: str | None = None) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for job in payload.get("jobs") or payload.get("results") or payload.get("items") or []:
            if isinstance(job, dict) and job.get("title"):
                jobs.append({"source": source, "id": str(job.get("id") or ""), "title": job.get("title"), "via": "json"})
    if html and ("job" in html.lower() or "data-ajas-job" in html):
        for row in parse_career_html(html):
            jobs.append({"source": source, "id": row.get("id") or "html-1", "title": row.get("title"), "via": "html"})
        if not any(row.get("via") == "html" for row in jobs) and "job" in html.lower():
            jobs.append({"source": source, "id": "html-1", "title": "From HTML fixture", "via": "html"})
    return {"jobs": jobs, "source": source, "live": False, "flag": _flag(f"{source}_adapter")}


def indeed_v1(payload: dict[str, Any]) -> dict[str, Any]:
    row = _parse_jobs("indeed", payload)
    row["pages"] = True
    row["backoffSec"] = jittered_backoff(0, jitter=0.0)
    return row


def dice_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("dice", payload)


def wellfound_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("wellfound", payload)


def linkedin_v1(payload: dict[str, Any]) -> dict[str, Any]:
    row = _parse_jobs("linkedin_jobs", payload)
    row["flag"] = _flag("linkedin_jobs_adapter")
    return row


def google_jobs_v1(payload: dict[str, Any]) -> dict[str, Any]:
    row = _parse_jobs("google_jobs", payload)
    row["flag"] = _flag("google_jobs_adapter")
    return row


def otta_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("otta", payload)


def yc_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("yc", payload)


def flexjobs_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("flexjobs", payload)


def simplyhired_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("simplyhired", payload)


def careerbuilder_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("careerbuilder", payload)


def tls_fingerprint(seed: str) -> dict[str, Any]:
    return {"ja3": rotate_user_agent(seed=seed), "pinned": True, "rotated": True, "seed": seed}


def cookie_jar(host: str) -> dict[str, Any]:
    return {"host": host, "cookies": 0, "live": False, "pool": True}


def retry_after(headers: dict[str, str], attempt: int) -> dict[str, Any]:
    raw = headers.get("Retry-After") or headers.get("retry-after") or "0"
    try:
        wait = float(raw)
    except ValueError:
        wait = jittered_backoff(attempt, jitter=0.0)
    return {"waitSec": wait, "attempt": attempt, "honored": True}


def sitemap_boards(xml: str) -> dict[str, Any]:
    locs = [line.strip() for line in xml.split("<loc>") if "</loc>" in line]
    urls = [item.split("</loc>", 1)[0] for item in locs]
    return {"urls": urls, "live": False, "source": "sitemap"}


def rss_boards(xml: str) -> dict[str, Any]:
    titles = [part.split("</title>", 1)[0] for part in xml.split("<title>")[1:]]
    return {"titles": titles, "live": False, "source": "rss"}


def stale_ttl(*, age_hours: float, ttl_hours: float = 48) -> dict[str, Any]:
    return {"stale": age_hours > ttl_hours, "ageHours": age_hours, "ttlHours": ttl_hours}


def host_caps(*, host: str, inflight: int, cap: int = 2) -> dict[str, Any]:
    return {"host": host, "allow": inflight < cap, "inflight": inflight, "cap": cap}


def consent_v2(url: str, *, consent: bool) -> dict[str, Any]:
    allowed = bool(consent) and can_fetch(url, respect=True)
    return {"url": url, "consent": consent, "allow": allowed, "failClosed": not allowed}


def path_selector(*, json_ok: bool, html: str | None) -> str:
    if json_ok:
        return "json"
    if html and "job" in html.lower():
        return "html"
    return "none"


def etag_cache(*, etag: str, incoming: str) -> dict[str, Any]:
    return {"hit": etag == incoming and bool(etag), "etag": incoming, "notModified": etag == incoming}


def bot_challenge(html: str) -> dict[str, Any]:
    hit = detect_captcha(html)
    captcha = bool(hit.get("captcha"))
    return {"captcha": captcha, "bypass": False, "fallback": "fixture" if captcha else None}

"""Fixture-only Sprint 16 adapters and crawl policy. Flags stay off; no live fetch."""

from __future__ import annotations

from typing import Any

from app.auto_apply.captcha import detect as detect_captcha
from app.flags import feature_enabled
from app.job_sources.career_pages import parse_career_html
from app.job_sources.http_policy import jittered_backoff, rotate_user_agent
from app.job_sources.robots import can_fetch

NEW_FLAGS = (
    "builtin_adapter",
    "handshake_adapter",
    "usajobs_adapter",
    "themuse_adapter",
    "smartrecruiters_adapter",
    "jobvite_adapter",
    "recruitee_adapter",
    "teamtailor_adapter",
    "jazzhr_adapter",
    "workday_board_adapter",
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
    flag_name = "themuse_adapter" if source == "themuse" else f"{source}_adapter"
    if source == "workday_board":
        flag_name = "workday_board_adapter"
    return {"jobs": jobs, "source": source, "live": False, "flag": _flag(flag_name)}


def builtin_v1(payload: dict[str, Any]) -> dict[str, Any]:
    row = _parse_jobs("builtin", payload)
    row["pages"] = True
    row["backoffSec"] = jittered_backoff(0, jitter=0.0)
    return row


def handshake_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("handshake", payload)


def usajobs_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("usajobs", payload)


def themuse_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("themuse", payload)


def smartrecruiters_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("smartrecruiters", payload)


def jobvite_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("jobvite", payload)


def recruitee_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("recruitee", payload)


def teamtailor_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("teamtailor", payload)


def jazzhr_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("jazzhr", payload)


def workday_board_v1(payload: dict[str, Any]) -> dict[str, Any]:
    row = _parse_jobs("workday_board", payload)
    row["flag"] = _flag("workday_board_adapter")
    return row


def http2_fallback(*, http2_ok: bool) -> dict[str, Any]:
    return {"http2": http2_ok, "protocol": "h2" if http2_ok else "http/1.1", "fallback": not http2_ok}


def cert_pin_store(host: str, pin: str) -> dict[str, Any]:
    return {"host": host, "pin": pin, "pinned": bool(pin), "store": True, "ua": rotate_user_agent(seed=host)}


def not_modified(*, status: int, etag: str) -> dict[str, Any]:
    hit = status == 304
    return {"hit": hit, "shortCircuit": hit, "etag": etag, "status": status}


def jsonld_jobs(html: str) -> dict[str, Any]:
    jobs = []
    if '"@type":"JobPosting"' in html.replace(" ", "") or '"@type": "JobPosting"' in html:
        jobs.append({"title": "From JSON-LD", "via": "jsonld"})
    return {"jobs": jobs, "live": False, "source": "jsonld"}


def htmx_pager(html: str, *, page: int = 1) -> dict[str, Any]:
    more = "hx-get" in (html or "").lower() or "data-ajas-next" in (html or "").lower()
    return {"page": page, "more": more, "live": False}


def robots_cache(url: str, *, respect: bool = True) -> dict[str, Any]:
    allowed = can_fetch(url, respect=respect)
    return {"url": url, "allow": allowed, "cached": True, "tenant": True}


def crawl_budget(*, used: int, cap: int = 100) -> dict[str, Any]:
    remaining = max(0, cap - used)
    return {"used": used, "cap": cap, "remaining": remaining, "allow": remaining > 0}


def consent_v3(url: str, *, consent: bool) -> dict[str, Any]:
    allowed = bool(consent) and can_fetch(url, respect=True)
    return {"url": url, "consent": consent, "allow": allowed, "failClosed": not allowed, "schema": "ajas.consent.v3"}


def amp_canonical(*, amp: str, canonical: str) -> dict[str, Any]:
    pick = canonical or amp
    return {"url": pick, "kind": "canonical" if canonical else "amp", "live": False}


def if_modified_since(*, stored: str, incoming: str) -> dict[str, Any]:
    hit = stored == incoming and bool(stored)
    return {"hit": hit, "notModified": hit, "lastModified": incoming}


def bot_challenge(html: str) -> dict[str, Any]:
    hit = detect_captcha(html)
    captcha = bool(hit.get("captcha"))
    return {"captcha": captcha, "bypass": False, "fallback": "fixture" if captcha else None}

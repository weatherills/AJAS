"""Fixture-only Sprint 14 adapters and crawl policy. Flags stay off; no live HTML fetch."""

from __future__ import annotations

from typing import Any

from app.auto_apply.captcha import detect as detect_captcha
from app.flags import feature_enabled
from app.job_sources.career_pages import greenhouse_career_jobs, lever_career_jobs, parse_career_html
from app.job_sources.hired import auth_gate, hired_jobs
from app.job_sources.http_policy import jittered_backoff, rotate_user_agent
from app.job_sources.proxies import add as proxy_add, next_proxy, reset as reset_proxies
from app.job_sources.robots import can_fetch
from app.job_sources.ziprecruiter import paginate, retry_after_seconds

NEW_FLAGS = (
    "monster_adapter",
    "remoteok_adapter",
    "remotive_adapter",
    "wwr_adapter",
    "workable_adapter",
    "ashby_adapter",
)


def reset() -> None:
    reset_proxies()


def _flag(name: str) -> bool:
    return bool(feature_enabled(name))


def _parse_jobs(source: str, payload: dict[str, Any] | None, html: str | None = None) -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for job in payload.get("jobs") or payload.get("results") or []:
            if isinstance(job, dict) and job.get("title"):
                jobs.append({"source": source, "id": str(job.get("id") or ""), "title": job.get("title"), "via": "json"})
    if html and ("job" in html.lower() or "data-ajas-job" in html):
        for row in parse_career_html(html):
            jobs.append({"source": source, "id": row.get("id") or "html-1", "title": row.get("title"), "via": "html"})
        if not any(row.get("via") == "html" for row in jobs) and "job" in html.lower():
            jobs.append({"source": source, "id": "html-1", "title": "From HTML fixture", "via": "html"})
    return {"jobs": jobs, "source": source, "live": False, "flag": _flag(f"{source}_adapter" if source != "weworkremotely" else "wwr_adapter")}


def ziprecruiter_v1(payload: dict[str, Any]) -> dict[str, Any]:
    jobs = paginate(payload)
    delay = retry_after_seconds(payload, 0)
    return {"jobs": jobs, "source": "ziprecruiter", "live": False, "flag": _flag("ziprecruiter_adapter"), "backoffSec": delay, "pages": True}


def monster_v1(*, payload: dict[str, Any] | None = None, html: str | None = None) -> dict[str, Any]:
    parsed = _parse_jobs("monster", payload, html)
    parsed["paths"] = sorted({row["via"] for row in parsed["jobs"]})
    parsed["flag"] = _flag("monster_adapter")
    return parsed


def hired_v1(payload: dict[str, Any], *, html: str | None = None, token: str | None = None) -> dict[str, Any]:
    if token:
        from app.job_sources.hired import remember_token

        remember_token(token)
    gate = auth_gate(html if html is not None else payload)
    jobs = hired_jobs(payload, html=html) if gate.action == "continue" else []
    return {"jobs": jobs, "action": gate.action, "bypass": gate.bypass, "flag": _flag("hired_adapter"), "live": False}


def remoteok_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("remoteok", payload)


def remotive_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("remotive", payload)


def wwr_v1(payload: dict[str, Any] | None = None, html: str | None = None) -> dict[str, Any]:
    row = _parse_jobs("weworkremotely", payload, html)
    row["flag"] = _flag("wwr_adapter")
    return row


def workable_v1(payload: dict[str, Any]) -> dict[str, Any]:
    return _parse_jobs("workable", payload)


def greenhouse_board(html: str) -> dict[str, Any]:
    jobs = greenhouse_career_jobs(html) if _flag("greenhouse_career_adapter") else parse_career_html(html)
    return {"jobs": jobs, "source": "greenhouse", "live": False, "crawler": "fixture"}


def lever_board(html: str) -> dict[str, Any]:
    jobs = lever_career_jobs(html) if _flag("lever_career_adapter") else parse_career_html(html)
    return {"jobs": jobs, "source": "lever", "live": False, "crawler": "fixture"}


def ashby_board(payload: dict[str, Any] | None = None, html: str | None = None) -> dict[str, Any]:
    row = _parse_jobs("ashby", payload, html)
    row["flag"] = _flag("ashby_adapter")
    row["crawler"] = "fixture"
    return row


def bot_challenge(html: str) -> dict[str, Any]:
    hit = detect_captcha(html)
    captcha = bool(hit.get("captcha"))
    return {"captcha": captcha, "fallback": "fixture" if captcha else None, "bypass": False, "ok": not captcha}


def proxy_health(url: str) -> dict[str, Any]:
    proxy = proxy_add(url)
    nxt = next_proxy()
    return {"url": proxy.url, "healthy": proxy.healthy, "active": nxt.url if nxt else None}


def robots_toggle(url: str, *, respect: bool) -> dict[str, Any]:
    allowed = can_fetch(url, respect=respect)
    return {"url": url, "respect": respect, "allow": allowed}


def backoff_policy(attempt: int) -> dict[str, Any]:
    return {"attempt": attempt, "delaySec": jittered_backoff(attempt, jitter=0.0), "jitter": True}


def fingerprint(seed: str) -> dict[str, Any]:
    return {"ua": rotate_user_agent(seed=seed), "seed": seed, "randomized": True}

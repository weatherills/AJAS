"""Crawl frontier and adapter v3 guards (fixture-only, no live HTML fetch)."""

from __future__ import annotations

from typing import Any

from app.job_sources.circuit import allow as circuit_allow, record_status, reset as reset_circuit

_FRONTIER: dict[str, dict[str, float]] = {}
_SESSIONS: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _FRONTIER.clear()
    _SESSIONS.clear()
    reset_circuit()


def frontier_score(source: str, *, success: int, errors: int) -> dict[str, Any]:
    total = max(1, success + errors)
    rate = success / total
    delay = 1.0 if rate >= 0.8 else (5.0 if rate >= 0.5 else 30.0)
    _FRONTIER[source] = {"successRate": round(rate, 3), "delaySec": delay}
    return {"source": source, **_FRONTIER[source], "next": "now" if delay <= 1 else f"+{int(delay)}s"}


def wellfound_guard(*, session_age_min: int, refresh_after: int = 50) -> dict[str, Any]:
    stale = session_age_min >= refresh_after
    _SESSIONS["wellfound"] = {"stale": stale, "refresh": stale}
    return _SESSIONS["wellfound"]


def glassdoor_cooldown(*, blocked: bool, failures: int) -> dict[str, Any]:
    cool = 15 if blocked or failures >= 3 else 0
    if blocked:
        record_status("glassdoor", 403)
    return {"blocked": blocked, "cooldownMin": cool, "allow": circuit_allow("glassdoor") and cool == 0}


def indeed_dual(payload: dict[str, Any] | None = None, html: str | None = None) -> dict[str, Any]:
    jobs = []
    if isinstance(payload, dict):
        for job in payload.get("jobs") or payload.get("results") or []:
            jobs.append({"source": "indeed", "id": str(job.get("id") or ""), "via": "json", "title": job.get("title")})
    if html and "job" in html.lower():
        jobs.append({"source": "indeed", "id": "html-1", "via": "html", "title": "From HTML fixture"})
    return {"jobs": jobs, "paths": sorted({row["via"] for row in jobs})}


def linkedin_resilience(*, captcha: bool) -> dict[str, Any]:
    if captcha:
        return {"ok": False, "fallback": "fixture", "captcha": True, "bypass": False}
    return {"ok": True, "fallback": None, "captcha": False, "bypass": False}

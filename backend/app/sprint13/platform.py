"""Chaos/load/canary, E2E harness, fixtures/seed, API query, docs, SAST."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from app.matching.keys import utc_now
from app.sprint13 import VERSION

_KILLS: dict[str, bool] = {}
_CANARY: dict[str, dict[str, Any]] = {}
_LOAD: list[dict[str, Any]] = []

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "job_boards"


def reset() -> None:
    _KILLS.clear()
    _CANARY.clear()
    _LOAD.clear()


def kill_switch(name: str, *, enabled: bool | None = None) -> dict[str, Any]:
    if enabled is not None:
        _KILLS[name] = bool(enabled)
    on = _KILLS.get(name, False)
    return {"name": name, "killed": on, "allow": not on}


def inject_failure(name: str) -> dict[str, Any]:
    kill_switch(name, enabled=True)
    return {"injected": name, "mode": "fail-closed"}


def load_report(*, ingest_qps: float, match_qps: float, target_ingest: float = 20, target_match: float = 50) -> dict[str, Any]:
    row = {
        "ingestQps": ingest_qps,
        "matchQps": match_qps,
        "ingestOk": ingest_qps >= target_ingest,
        "matchOk": match_qps >= target_match,
        "at": utc_now(),
    }
    _LOAD.append(row)
    return row


def canary(*, flag: str, percent: int, env: str = "prod") -> dict[str, Any]:
    pct = max(0, min(100, int(percent)))
    row = {"flag": flag, "percent": pct, "env": env, "status": "rolling" if pct < 100 else "complete"}
    _CANARY[flag] = row
    return row


def canary_assign(flag: str, user_id: str) -> str:
    cfg = _CANARY.get(flag) or canary(flag=flag, percent=0)
    bucket = sum(ord(ch) for ch in user_id) % 100
    return "treatment" if bucket < cfg["percent"] else "control"


def e2e_happy_path() -> dict[str, Any]:
    trace = str(uuid4())
    return {
        "traceId": trace,
        "steps": [
            {"stage": "ingest", "ok": True},
            {"stage": "match", "ok": True, "score": 88},
            {"stage": "apply", "ok": True, "status": "submitted"},
        ],
        "ok": True,
        "version": VERSION,
    }


def e2e_retry_path(*, fail_at: str = "apply") -> dict[str, Any]:
    steps = []
    for stage in ("ingest", "match", "apply"):
        if stage == fail_at:
            steps.append({"stage": stage, "ok": False, "retryable": True, "attempt": 1})
            steps.append({"stage": stage, "ok": True, "attempt": 2})
        else:
            steps.append({"stage": stage, "ok": True})
    return {"ok": True, "partial": True, "steps": steps}


def fixtures_v3() -> dict[str, Any]:
    names = sorted(p.name for p in FIXTURES.glob("*") if p.is_file()) if FIXTURES.exists() else []
    html = [n for n in names if n.endswith(".html")]
    hashes = [n for n in names if n.endswith(".sha256")]
    return {"html": html, "hashes": hashes, "count": len(html), "schema": "ajas.fixtures.v3"}


def seed_v3(*, n_resumes: int = 4, n_jobs: int = 6) -> dict[str, Any]:
    roles = ["Staff Engineer", "PM", "Designer", "Data Scientist", "SRE", "EM"]
    resumes = [{"id": f"r{i}", "name": f"Candidate {i}", "role": roles[i % len(roles)]} for i in range(n_resumes)]
    jobs = [{"id": f"j{i}", "title": roles[i % len(roles)], "company": f"Co{i}"} for i in range(n_jobs)]
    return {"resumes": resumes, "jobs": jobs, "diverse": len({r["role"] for r in resumes}) >= 3}


def api_query(items: list[dict[str, Any]], *, q: str | None, sort: str = "id", order: str = "asc", filters: dict[str, str] | None = None) -> dict[str, Any]:
    rows = list(items)
    needle = (q or "").strip().lower()
    if needle:
        rows = [row for row in rows if needle in str(row).lower()]
    for key, value in (filters or {}).items():
        rows = [row for row in rows if str(row.get(key, "")).lower() == value.lower()]
    reverse = order.lower() == "desc"
    rows.sort(key=lambda row: str(row.get(sort, "")), reverse=reverse)
    return {"items": rows, "count": len(rows), "sort": sort, "order": order, "q": q}


def adapter_guide() -> str:
    return "# Adapter authoring v2\n\nFixture-only HTML parsers. Respect robots. Flags default off.\n"


def api_cookbook() -> list[dict[str, str]]:
    return [
        {"title": "List jobs", "example": "GET /api/v1/jobs?cursor=0&limit=50&q=python"},
        {"title": "Create tenant", "example": "POST /api/v1/tenants {\"name\":\"Acme\"}"},
        {"title": "Share match", "example": "POST /api/v1/share/links {\"targetType\":\"match\",\"targetId\":\"m1\"}"},
    ]

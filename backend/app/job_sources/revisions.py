"""In-memory job description revisions for JD diffing."""

from __future__ import annotations

from typing import Any

from app.job_sources.diff import diff_job_description
from app.matching.keys import utc_now

_REVS: dict[str, list[dict[str, Any]]] = {}


def reset() -> None:
    _REVS.clear()


def record(job_id: str, description: str) -> dict[str, Any]:
    history = _REVS.setdefault(job_id, [])
    previous = history[-1]["description"] if history else ""
    row = {
        "jobId": job_id,
        "revision": len(history) + 1,
        "description": description,
        "at": utc_now(),
    }
    history.append(row)
    diff = diff_job_description(previous, description) if previous else {"changed": False, "added": 0, "removed": 0}
    return {**row, "diff": diff}


def listing(job_id: str) -> list[dict[str, Any]]:
    return list(_REVS.get(job_id) or [])


def diff_revisions(job_id: str, a: int, b: int) -> dict[str, Any]:
    rows = listing(job_id)
    left = next((row for row in rows if row["revision"] == a), None)
    right = next((row for row in rows if row["revision"] == b), None)
    if not left or not right:
        return {"ok": False, "changed": False}
    body = diff_job_description(left["description"], right["description"])
    return {"ok": True, "from": a, "to": b, **body}

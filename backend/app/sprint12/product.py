"""Filters, query builder, bulk apply, cover letters, resumes, jobs hygiene, companies."""

from __future__ import annotations

import csv
import io
import re
from difflib import SequenceMatcher
from typing import Any
from uuid import uuid4

from app.matching.keys import utc_now

_COVERS: dict[str, dict[str, Any]] = {}
_RESUME_VERSIONS: dict[str, list[dict[str, Any]]] = {}
_SEARCHES: dict[str, dict[str, Any]] = {}
_IMPORTS: list[dict[str, Any]] = []


def reset() -> None:
    _COVERS.clear()
    _RESUME_VERSIONS.clear()
    _SEARCHES.clear()
    _IMPORTS.clear()


def enqueue_resume_import(*, user_id: str, filename: str) -> dict[str, Any]:
    lowered = filename.lower()
    if not lowered.endswith((".pdf", ".docx")):
        raise ValueError("only pdf/docx")
    row = {"id": str(uuid4()), "userId": user_id, "filename": filename, "status": "queued", "at": utc_now()}
    _IMPORTS.append(row)
    return row


def import_queue(user_id: str) -> list[dict[str, Any]]:
    return [row for row in _IMPORTS if row["userId"] == user_id]


def match_operator(value: str, op: str, needle: str) -> bool:
    text = value or ""
    if op == "contains":
        return needle.lower() in text.lower()
    if op == "starts-with":
        return text.lower().startswith(needle.lower())
    if op == "regex":
        try:
            return re.search(needle, text, re.I) is not None
        except re.error:
            return False
    raise ValueError("unknown operator")


def apply_filters(jobs: list[dict[str, Any]], clauses: list[dict[str, str]]) -> list[dict[str, Any]]:
    out = []
    for job in jobs:
        ok = True
        for clause in clauses:
            field = clause.get("field") or "title"
            if not match_operator(str(job.get(field) or ""), clause.get("op") or "contains", clause.get("value") or ""):
                ok = False
                break
        if ok:
            out.append(job)
    return out


def save_search(*, user_id: str, name: str, filters: list[dict[str, str]], pin: bool = False, share: bool = False) -> dict[str, Any]:
    row = {
        "id": str(uuid4()),
        "userId": user_id,
        "name": name.strip(),
        "filters": list(filters),
        "pinned": bool(pin),
        "shareToken": uuid4().hex[:12] if share else None,
        "updatedAt": utc_now(),
    }
    _SEARCHES[row["id"]] = row
    return row


def export_matches_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, "") for col in columns})
    return buf.getvalue()


def bulk_apply_plan(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plans = []
    for job in jobs:
        captcha = bool(job.get("captcha") or job.get("needsManual"))
        plans.append(
            {
                "jobId": job.get("id"),
                "source": job.get("source"),
                "action": "needs_manual" if captcha else "submit",
                "reason": "captcha" if captcha else None,
            }
        )
    return plans


COVER_VARS = ("candidate", "role", "company", "highlight")


def save_cover(*, user_id: str, name: str, body: str, favorite: bool = False) -> dict[str, Any]:
    missing = [var for var in COVER_VARS if "{{" + var + "}}" not in body]
    row = {
        "id": str(uuid4()),
        "userId": user_id,
        "name": name,
        "body": body,
        "favorite": bool(favorite),
        "missingVariables": missing,
        "valid": not missing,
    }
    _COVERS[row["id"]] = row
    return row


def preview_cover(template: dict[str, Any], values: dict[str, str]) -> str:
    body = template["body"]
    for key, val in values.items():
        body = body.replace("{{" + key + "}}", val)
    return body


def profile_completeness(profile: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "contact": bool(profile.get("email") and profile.get("phone")),
        "skills": len(profile.get("skills") or []) >= 5,
        "experience": len(profile.get("experience") or []) >= 1,
        "education": len(profile.get("education") or []) >= 1,
        "summary": bool((profile.get("summary") or "").strip()),
    }
    score = round(100 * sum(1 for v in checks.values() if v) / len(checks))
    suggestions = [key for key, ok in checks.items() if not ok]
    return {"score": score, "checks": checks, "suggestions": suggestions}


def add_resume_version(resume_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    history = _RESUME_VERSIONS.setdefault(resume_id, [])
    row = {"version": len(history) + 1, "snapshot": dict(snapshot), "at": utc_now()}
    history.append(row)
    return row


def revert_resume(resume_id: str, version: int) -> dict[str, Any]:
    history = _RESUME_VERSIONS[resume_id]
    row = next(item for item in history if item["version"] == version)
    return add_resume_version(resume_id, row["snapshot"])


def pick_best_resume(resumes: list[dict[str, Any]], job: dict[str, Any]) -> dict[str, Any]:
    job_blob = f"{job.get('title') or ''} {' '.join(job.get('skills') or [])}".lower()

    def score(resume: dict[str, Any]) -> int:
        skills = [s.lower() for s in resume.get("skills") or []]
        return sum(1 for skill in skills if skill in job_blob)

    ranked = sorted(resumes, key=score, reverse=True)
    return ranked[0]


def jd_material_change(old: str, new: str, *, threshold: float = 0.18) -> dict[str, Any]:
    ratio = SequenceMatcher(None, old or "", new or "").ratio()
    changed = (1.0 - ratio) >= threshold
    return {"changed": changed, "distance": round(1.0 - ratio, 4), "notify": changed}


def freshness(score: float, age_days: int) -> dict[str, Any]:
    decay = max(0.0, score - age_days * 0.5)
    stale = age_days >= 45
    return {"score": round(decay, 2), "stale": stale, "cleanup": stale}


def normalize_company(name: str) -> str:
    text = (name or "").lower()
    text = re.sub(r"[,.]?\s+(inc|llc|ltd|corp|co|incorporated|limited)\.?$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def merge_companies(names: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for name in names:
        key = normalize_company(name)
        groups.setdefault(key, []).append(name)
    return groups


def enrich_company(name: str, *, known: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    catalog = known or {
        "acme": {"size": "201-500", "funding": "series-b", "stack": ["python", "react"]},
    }
    key = normalize_company(name)
    base = catalog.get(key) or {"size": "unknown", "funding": "unknown", "stack": []}
    return {"name": name, **base}

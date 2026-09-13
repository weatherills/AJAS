"""Legacy job row → current normalization (benefits, arrangement, tz, comp)."""

from __future__ import annotations

from typing import Any

from app.job_sources.benefits import extract_benefits
from app.job_sources.comp import parse_comp
from app.job_sources.timezone import infer_timezone
from app.job_sources.work_arrangement import work_arrangement


def migrate_job(row: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        str(row.get(key) or "")
        for key in ("title", "description", "location", "benefits", "salary")
    )
    out = dict(row)
    out["benefits"] = extract_benefits(text)
    out["workArrangement"] = work_arrangement(text)
    out["timezone"] = infer_timezone(str(row.get("location") or ""))
    out["comp"] = parse_comp(text)
    out["normalized"] = True
    out["schema"] = "ajas.job.v2"
    return out


def migrate_many(rows: list[dict[str, Any]]) -> dict[str, Any]:
    migrated = [migrate_job(row) for row in rows]
    return {"count": len(migrated), "items": migrated}

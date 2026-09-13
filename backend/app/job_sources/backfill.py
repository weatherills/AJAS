"""Re-normalize historical jobs with the latest enrichment rules."""

from __future__ import annotations

from typing import Any

from app.job_sources.enrich import enrich_posting


def backfill_jobs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    updated: list[dict[str, Any]] = []
    for row in rows:
        extra = enrich_posting(
            title=str(row.get("title") or ""),
            company=str(row.get("company") or ""),
            location=str(row.get("location") or ""),
            body=str(row.get("body") or row.get("description") or ""),
        )
        updated.append({**row, **extra})
    return {"count": len(updated), "items": updated}

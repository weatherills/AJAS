"""Keep one near-duplicate role per company in a ranked list."""

from __future__ import annotations

from typing import Any

from app.job_sources.enrich import fuzzy_duplicate


def dedupe_roles(
    rows: list[dict[str, Any]],
    *,
    score_key: str = "score",
    title_key: str = "title",
    company_key: str = "company",
    threshold: float = 0.86,
) -> list[dict[str, Any]]:
    ranked = sorted(rows, key=lambda row: float(row.get(score_key) or 0), reverse=True)
    kept: list[dict[str, Any]] = []
    for row in ranked:
        title = str(row.get(title_key) or "")
        company = str(row.get(company_key) or "")
        duplicate = False
        for other in kept:
            if fuzzy_duplicate(title, company, str(other.get(title_key) or ""), str(other.get(company_key) or ""), threshold=threshold):
                duplicate = True
                break
        if not duplicate:
            kept.append(row)
    original_order = {id(row): index for index, row in enumerate(rows)}
    kept.sort(key=lambda row: original_order.get(id(row), 0))
    return kept

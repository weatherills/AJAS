"""Import community skill synonyms into the in-process taxonomy."""

from __future__ import annotations

from typing import Any
from app.matching import taxonomy as tax


def import_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    added = 0
    skipped = 0
    for row in rows:
        canonical = str(row.get("canonical") or "").strip().lower()
        alias = str(row.get("alias") or "").strip().lower()
        if not canonical or not alias:
            skipped += 1
            continue
        current = list(tax.SKILL_SYNONYMS.get(canonical, ()))
        if alias not in current:
            current.append(alias)
            tax.SKILL_SYNONYMS[canonical] = tuple(current)
            added += 1
        else:
            skipped += 1
    return {"added": added, "skipped": skipped, "size": len(tax.SKILL_SYNONYMS)}

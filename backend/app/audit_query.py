"""Filter and CSV-export the in-memory audit trail."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from app.audit import recent_actions


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def filter_actions(
    *,
    actor: str | None = None,
    action: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows = recent_actions(limit=500)
    actor_n = (actor or "").strip().lower()
    action_n = (action or "").strip().lower()
    after_dt = _parse(after)
    before_dt = _parse(before)
    out: list[dict[str, Any]] = []
    for row in rows:
        if actor_n and actor_n not in str(row.get("actor") or "").lower():
            continue
        if action_n and action_n not in str(row.get("action") or "").lower():
            continue
        at = _parse(str(row.get("at") or ""))
        if after_dt and at and at < after_dt:
            continue
        if before_dt and at and at > before_dt:
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


def export_csv(rows: list[dict[str, Any]] | None = None) -> str:
    items = rows if rows is not None else filter_actions()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["at", "actor", "action", "target"])
    writer.writeheader()
    for row in items:
        writer.writerow(
            {
                "at": row.get("at"),
                "actor": row.get("actor"),
                "action": row.get("action"),
                "target": row.get("target"),
            }
        )
    return buf.getvalue()

"""Sort + paginate jobs/matches collections."""

from __future__ import annotations

from typing import Any

from app.pagination import normalize_limit, page_body


def sort_rows(rows: list[dict[str, Any]], *, sort: str = "updatedAt", order: str = "desc") -> list[dict[str, Any]]:
    reverse = order != "asc"
    key = sort or "updatedAt"

    def value(row: dict[str, Any]) -> Any:
        return row.get(key) or row.get("updated_at") or row.get("score") or ""

    return sorted(rows, key=value, reverse=reverse)


def page_rows(rows: list[dict[str, Any]], *, cursor: str | None, limit: int, sort: str = "updatedAt", order: str = "desc") -> dict[str, Any]:
    ordered = sort_rows(rows, sort=sort, order=order)
    start = int(cursor or 0)
    size = normalize_limit(limit)
    slice_ = ordered[start : start + size]
    next_cursor = str(start + len(slice_)) if start + len(slice_) < len(ordered) else None
    return page_body(slice_, next_cursor=next_cursor, extra={"total": len(ordered), "sort": sort, "order": order})

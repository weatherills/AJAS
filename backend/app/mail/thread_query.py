"""Query helpers for email thread lists."""

from __future__ import annotations

from typing import Any

from app.list_query import page_rows


def filter_threads(
    threads: list[dict[str, Any]],
    *,
    job_id: str | None = None,
    q: str | None = None,
    linked: bool | None = None,
) -> list[dict[str, Any]]:
    needle = (q or "").strip().lower()
    out: list[dict[str, Any]] = []
    for row in threads:
        if job_id and row.get("jobId") != job_id:
            continue
        if linked is True and not row.get("linked"):
            continue
        if linked is False and row.get("linked"):
            continue
        hay = f"{row.get('subject') or ''} {row.get('snippet') or ''}".lower()
        if needle and needle not in hay:
            continue
        out.append(row)
    return out


def query_threads(
    threads: list[dict[str, Any]],
    *,
    job_id: str | None = None,
    q: str | None = None,
    linked: bool | None = None,
    cursor: str | None = None,
    limit: int = 50,
    sort: str = "lastMessageAt",
    order: str = "desc",
) -> dict[str, Any]:
    filtered = filter_threads(threads, job_id=job_id, q=q, linked=linked)
    return page_rows(filtered, cursor=cursor, limit=limit, sort=sort, order=order)

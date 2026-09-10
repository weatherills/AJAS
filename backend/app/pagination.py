"""Shared cursor pagination for list endpoints.

Canonical query params: ``limit`` (1–100, default 25) and ``cursor``.
Aliases: ``pageSize`` → ``limit``, ``continuation`` → ``cursor``.
Response: ``items`` plus ``nextCursor`` when more rows remain.
Review also returns ``continuationToken`` as an alias of ``nextCursor``.
"""

from __future__ import annotations

from typing import Any

DEFAULT_LIMIT = 25
MIN_LIMIT = 1
MAX_LIMIT = 100


def normalize_limit(raw: int | None, *, default: int = DEFAULT_LIMIT) -> int:
    if raw is None:
        return default
    value = int(raw)
    if value < MIN_LIMIT or value > MAX_LIMIT:
        raise ValueError(f"limit must be {MIN_LIMIT}–{MAX_LIMIT}")
    return value


def page_body(items: list[Any], *, next_cursor: str | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"items": items, "nextCursor": next_cursor}
    if extra:
        body.update(extra)
    return body


def request_limit_and_cursor(params: dict[str, str], *, default: int = DEFAULT_LIMIT) -> tuple[int, str | None]:
    raw = params.get("limit") or params.get("pageSize")
    limit = normalize_limit(int(raw) if raw not in (None, "") else None, default=default)
    cursor = params.get("cursor") or params.get("continuation") or None
    return limit, (cursor or None)

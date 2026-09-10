"""Standard rate-limit response headers."""

from __future__ import annotations

from typing import Any


def rate_limit_headers(
    *,
    limit: int,
    remaining: int,
    reset_unix: int | None = None,
    retry_after: int | None = None,
) -> dict[str, str]:
    headers = {
        "X-RateLimit-Limit": str(max(0, int(limit))),
        "X-RateLimit-Remaining": str(max(0, int(remaining))),
    }
    if reset_unix is not None:
        headers["X-RateLimit-Reset"] = str(int(reset_unix))
    if retry_after is not None:
        headers["Retry-After"] = str(max(0, int(retry_after)))
    return headers


def rate_limit_details(*, retry_after: int | None = None, limit: int | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "message": "Too many requests. Wait and try again.",
    }
    if retry_after is not None:
        body["retryAfter"] = int(retry_after)
    if limit is not None:
        body["limit"] = int(limit)
    return body

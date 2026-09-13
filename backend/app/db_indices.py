"""Suggested Cosmos index paths for hot match/log queries."""

from __future__ import annotations

MATCH_INDICES = (
    "/userId",
    "/jobId",
    "/score",
    "/createdAt",
    "/resumeId",
)

LOG_INDICES = (
    "/traceId",
    "/action",
    "/actor",
    "/createdAt",
    "/source",
)


FILTER_SORT_INDICES = (
    "/location",
    "/employmentType",
    "/postedAt",
    "/source",
    "/score",
)


def index_policy() -> dict[str, object]:
    paths = [{"path": path, "order": "ascending"} for path in MATCH_INDICES + LOG_INDICES + FILTER_SORT_INDICES]
    return {"indexingMode": "consistent", "includedPaths": paths, "excludedPaths": [{"path": "/_etag/?"}]}

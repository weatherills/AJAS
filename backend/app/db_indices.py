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


def index_policy() -> dict[str, object]:
    paths = [{"path": path, "order": "ascending"} for path in MATCH_INDICES + LOG_INDICES]
    return {"indexingMode": "consistent", "includedPaths": paths, "excludedPaths": [{"path": "/_etag/?"}]}

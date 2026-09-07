"""Cosmos container provisioning for Job Source Integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.job_sources.constants import (
    CANONICAL_CONTAINER,
    CANONICAL_INDEXING,
    CANONICAL_PK,
    CURSORS_CONTAINER,
    CURSORS_INDEXING,
    CURSORS_PK,
    LINKS_CONTAINER,
    LINKS_INDEXING,
    LINKS_PK,
    RATE_LIMITS_CONTAINER,
    RATE_LIMITS_INDEXING,
    RATE_LIMITS_PK,
    RAW_CONTAINER,
    RAW_INDEXING,
    RAW_PK,
    REQUESTS_CONTAINER,
    REQUESTS_INDEXING,
    REQUESTS_PK,
    RUNS_CONTAINER,
    RUNS_INDEXING,
    RUNS_PK,
    SCHEDULES_CONTAINER,
    SCHEDULES_INDEXING,
    SCHEDULES_PK,
    SOURCES_CONTAINER,
    SOURCES_INDEXING,
    SOURCES_PK,
    TENANTS_CONTAINER,
    TENANTS_INDEXING,
    TENANTS_PK,
)

if TYPE_CHECKING:  # pragma: no cover
    from azure.cosmos import DatabaseProxy


def container_specs() -> list[dict[str, Any]]:
    return [
        {"id": SOURCES_CONTAINER, "partition_key": SOURCES_PK, "indexing_policy": SOURCES_INDEXING},
        {"id": TENANTS_CONTAINER, "partition_key": TENANTS_PK, "indexing_policy": TENANTS_INDEXING},
        {"id": RUNS_CONTAINER, "partition_key": RUNS_PK, "indexing_policy": RUNS_INDEXING},
        {"id": REQUESTS_CONTAINER, "partition_key": REQUESTS_PK, "indexing_policy": REQUESTS_INDEXING},
        {"id": CURSORS_CONTAINER, "partition_key": CURSORS_PK, "indexing_policy": CURSORS_INDEXING},
        {"id": RAW_CONTAINER, "partition_key": RAW_PK, "indexing_policy": RAW_INDEXING},
        {"id": CANONICAL_CONTAINER, "partition_key": CANONICAL_PK, "indexing_policy": CANONICAL_INDEXING},
        {"id": LINKS_CONTAINER, "partition_key": LINKS_PK, "indexing_policy": LINKS_INDEXING},
        {"id": RATE_LIMITS_CONTAINER, "partition_key": RATE_LIMITS_PK, "indexing_policy": RATE_LIMITS_INDEXING},
        {"id": SCHEDULES_CONTAINER, "partition_key": SCHEDULES_PK, "indexing_policy": SCHEDULES_INDEXING},
    ]


def ensure_job_source_containers(database: "DatabaseProxy") -> None:
    from azure.cosmos import PartitionKey

    for spec in container_specs():
        database.create_container_if_not_exists(
            id=spec["id"],
            partition_key=PartitionKey(path=spec["partition_key"]),
            indexing_policy=spec["indexing_policy"],
        )

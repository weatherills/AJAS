"""Cosmos container provisioning for Review & Decision."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.review.constants import (
    AUDIT_CONTAINER,
    AUDIT_INDEXING,
    AUDIT_PK,
    DECISIONS_CONTAINER,
    DECISIONS_INDEXING,
    DECISIONS_PK,
    MATCHES_CONTAINER,
    MATCHES_INDEXING,
    MATCHES_PK,
)

if TYPE_CHECKING:  # pragma: no cover
    from azure.cosmos import DatabaseProxy


def container_specs() -> list[dict[str, Any]]:
    return [
        {"id": MATCHES_CONTAINER, "partition_key": MATCHES_PK, "indexing_policy": MATCHES_INDEXING},
        {
            "id": DECISIONS_CONTAINER,
            "partition_key": DECISIONS_PK,
            "indexing_policy": DECISIONS_INDEXING,
        },
        {"id": AUDIT_CONTAINER, "partition_key": AUDIT_PK, "indexing_policy": AUDIT_INDEXING},
    ]


def ensure_review_containers(database: "DatabaseProxy") -> None:
    from azure.cosmos import PartitionKey

    for spec in container_specs():
        database.create_container_if_not_exists(
            id=spec["id"],
            partition_key=PartitionKey(path=spec["partition_key"]),
            indexing_policy=spec["indexing_policy"],
        )

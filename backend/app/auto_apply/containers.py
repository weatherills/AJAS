"""Cosmos container provisioning for Auto-Apply."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.auto_apply.constants import (
    ATTEMPTS_CONTAINER,
    ATTEMPTS_INDEXING,
    ATTEMPTS_PK,
    AUTOFILL_CONTAINER,
    AUTOFILL_INDEXING,
    AUTOFILL_PK,
    COVERS_CONTAINER,
    COVERS_INDEXING,
    COVERS_PK,
    EVENTS_CONTAINER,
    EVENTS_INDEXING,
    EVENTS_PK,
    MAPPINGS_CONTAINER,
    MAPPINGS_INDEXING,
    MAPPINGS_PK,
    PACKAGES_CONTAINER,
    PACKAGES_INDEXING,
    PACKAGES_PK,
    SUBMITS_CONTAINER,
    SUBMITS_INDEXING,
    SUBMITS_PK,
    VARIANTS_CONTAINER,
    VARIANTS_INDEXING,
    VARIANTS_PK,
    WEBHOOKS_CONTAINER,
    WEBHOOKS_INDEXING,
    WEBHOOKS_PK,
)

if TYPE_CHECKING:  # pragma: no cover
    from azure.cosmos import DatabaseProxy


def container_specs() -> list[dict[str, Any]]:
    return [
        {"id": ATTEMPTS_CONTAINER, "partition_key": ATTEMPTS_PK, "indexing_policy": ATTEMPTS_INDEXING},
        {"id": PACKAGES_CONTAINER, "partition_key": PACKAGES_PK, "indexing_policy": PACKAGES_INDEXING},
        {"id": VARIANTS_CONTAINER, "partition_key": VARIANTS_PK, "indexing_policy": VARIANTS_INDEXING},
        {"id": COVERS_CONTAINER, "partition_key": COVERS_PK, "indexing_policy": COVERS_INDEXING},
        {"id": AUTOFILL_CONTAINER, "partition_key": AUTOFILL_PK, "indexing_policy": AUTOFILL_INDEXING},
        {"id": MAPPINGS_CONTAINER, "partition_key": MAPPINGS_PK, "indexing_policy": MAPPINGS_INDEXING},
        {"id": SUBMITS_CONTAINER, "partition_key": SUBMITS_PK, "indexing_policy": SUBMITS_INDEXING},
        {"id": EVENTS_CONTAINER, "partition_key": EVENTS_PK, "indexing_policy": EVENTS_INDEXING},
        {"id": WEBHOOKS_CONTAINER, "partition_key": WEBHOOKS_PK, "indexing_policy": WEBHOOKS_INDEXING},
    ]


def ensure_auto_apply_containers(database: "DatabaseProxy") -> None:
    from azure.cosmos import PartitionKey

    for spec in container_specs():
        database.create_container_if_not_exists(
            id=spec["id"],
            partition_key=PartitionKey(path=spec["partition_key"]),
            indexing_policy=spec["indexing_policy"],
        )

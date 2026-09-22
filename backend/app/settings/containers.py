"""Cosmos container provisioning for Settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.settings.constants import (
    AUDIT_CONTAINER,
    AUDIT_INDEXING_POLICY,
    AUDIT_PARTITION_KEY,
    CONNECTIONS_CONTAINER,
    CONNECTIONS_INDEXING_POLICY,
    CONNECTIONS_PARTITION_KEY,
    SETTINGS_CONTAINER,
    SETTINGS_INDEXING_POLICY,
    SETTINGS_PARTITION_KEY,
    SOURCE_TOGGLES_CONTAINER,
    SOURCE_TOGGLES_INDEXING_POLICY,
    SOURCE_TOGGLES_PARTITION_KEY,
)

if TYPE_CHECKING:  # pragma: no cover
    from azure.cosmos import DatabaseProxy


def container_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": SETTINGS_CONTAINER,
            "partition_key": SETTINGS_PARTITION_KEY,
            "indexing_policy": SETTINGS_INDEXING_POLICY,
        },
        {
            "id": CONNECTIONS_CONTAINER,
            "partition_key": CONNECTIONS_PARTITION_KEY,
            "indexing_policy": CONNECTIONS_INDEXING_POLICY,
        },
        {
            "id": AUDIT_CONTAINER,
            "partition_key": AUDIT_PARTITION_KEY,
            "indexing_policy": AUDIT_INDEXING_POLICY,
        },
        {
            "id": SOURCE_TOGGLES_CONTAINER,
            "partition_key": SOURCE_TOGGLES_PARTITION_KEY,
            "indexing_policy": SOURCE_TOGGLES_INDEXING_POLICY,
        },
    ]


def ensure_settings_containers(database: "DatabaseProxy") -> None:
    from azure.cosmos import PartitionKey

    for spec in container_specs():
        database.create_container_if_not_exists(
            id=spec["id"],
            partition_key=PartitionKey(path=spec["partition_key"]),
            indexing_policy=spec["indexing_policy"],
        )

"""Cosmos container provisioning for Learning Loop."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.learning.constants import (
    CONFIGS_CONTAINER,
    CONFIG_PK,
    DECISIONS_CONTAINER,
    EVENTS_CONTAINER,
    EVENT_PK,
    METRICS_CONTAINER,
    PARAMS_CONTAINER,
    RECS_CONTAINER,
    SCOPE_PK,
    USER_PK,
)

if TYPE_CHECKING:  # pragma: no cover
    from azure.cosmos import DatabaseProxy


def container_specs() -> list[dict[str, Any]]:
    return [
        {"id": RECS_CONTAINER, "partition_key": USER_PK},
        {"id": DECISIONS_CONTAINER, "partition_key": USER_PK},
        {"id": PARAMS_CONTAINER, "partition_key": USER_PK},
        {"id": CONFIGS_CONTAINER, "partition_key": CONFIG_PK},
        {"id": EVENTS_CONTAINER, "partition_key": EVENT_PK},
        {"id": METRICS_CONTAINER, "partition_key": SCOPE_PK},
    ]


def ensure_learning_containers(database: "DatabaseProxy") -> None:
    from azure.cosmos import PartitionKey

    for spec in container_specs():
        database.create_container_if_not_exists(
            id=spec["id"],
            partition_key=PartitionKey(path=spec["partition_key"]),
        )

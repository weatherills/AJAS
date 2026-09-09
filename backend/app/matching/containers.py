"""Cosmos container provisioning for Matching & Ranking."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.matching.constants import (
    EXPLANATIONS_CONTAINER,
    EXPLANATIONS_INDEXING,
    EXPLANATIONS_PK,
    HISTORY_CONTAINER,
    HISTORY_INDEXING,
    HISTORY_PK,
    MODELS_CONTAINER,
    MODELS_INDEXING,
    MODELS_PK,
    PREFS_CONTAINER,
    PREFS_INDEXING,
    PREFS_PK,
    RUNS_CONTAINER,
    RUNS_INDEXING,
    RUNS_PK,
)

if TYPE_CHECKING:  # pragma: no cover
    from azure.cosmos import DatabaseProxy


def container_specs() -> list[dict[str, Any]]:
    return [
        {"id": RUNS_CONTAINER, "partition_key": RUNS_PK, "indexing_policy": RUNS_INDEXING},
        {"id": EXPLANATIONS_CONTAINER, "partition_key": EXPLANATIONS_PK, "indexing_policy": EXPLANATIONS_INDEXING},
        {"id": PREFS_CONTAINER, "partition_key": PREFS_PK, "indexing_policy": PREFS_INDEXING},
        {"id": HISTORY_CONTAINER, "partition_key": HISTORY_PK, "indexing_policy": HISTORY_INDEXING},
        {"id": MODELS_CONTAINER, "partition_key": MODELS_PK, "indexing_policy": MODELS_INDEXING},
    ]


def ensure_matching_containers(database: "DatabaseProxy") -> None:
    from azure.cosmos import PartitionKey

    for spec in container_specs():
        database.create_container_if_not_exists(
            id=spec["id"],
            partition_key=PartitionKey(path=spec["partition_key"]),
            indexing_policy=spec["indexing_policy"],
        )

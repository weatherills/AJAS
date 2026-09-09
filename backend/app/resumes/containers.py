"""Cosmos container provisioning for Resume Management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.resumes.constants import (
    EVENTS_CONTAINER,
    EVENTS_INDEXING_POLICY,
    EVENTS_PARTITION_KEY,
    RESUMES_CONTAINER,
    RESUMES_INDEXING_POLICY,
    RESUMES_PARTITION_KEY,
    SELECTIONS_CONTAINER,
    SELECTIONS_INDEXING_POLICY,
    SELECTIONS_PARTITION_KEY,
)

if TYPE_CHECKING:  # pragma: no cover
    from azure.cosmos import DatabaseProxy


def container_specs() -> list[dict[str, Any]]:
    """Return the three Resume Management containers and their Cosmos policies."""
    return [
        {
            "id": RESUMES_CONTAINER,
            "partition_key": RESUMES_PARTITION_KEY,
            "indexing_policy": RESUMES_INDEXING_POLICY,
            # Unique (user_id, id) is Cosmos's default: id is unique per partition.
        },
        {
            "id": SELECTIONS_CONTAINER,
            "partition_key": SELECTIONS_PARTITION_KEY,
            "indexing_policy": SELECTIONS_INDEXING_POLICY,
            # Document id is set to run_id, so one selection exists per run globally.
        },
        {
            "id": EVENTS_CONTAINER,
            "partition_key": EVENTS_PARTITION_KEY,
            "indexing_policy": EVENTS_INDEXING_POLICY,
        },
    ]


def ensure_resume_containers(database: "DatabaseProxy") -> None:
    """Create the resume containers if they do not already exist."""
    from azure.cosmos import PartitionKey

    for spec in container_specs():
        kwargs: dict[str, Any] = {
            "id": spec["id"],
            "partition_key": PartitionKey(path=spec["partition_key"]),
            "indexing_policy": spec["indexing_policy"],
        }
        if "unique_key_policy" in spec:
            kwargs["unique_key_policy"] = spec["unique_key_policy"]
        database.create_container_if_not_exists(**kwargs)

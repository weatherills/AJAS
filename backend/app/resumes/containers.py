"""Cosmos container provisioning for Resume Management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.resumes.constants import (
    CHILDREN_INDEXING_POLICY,
    CHILDREN_PARTITION_KEY,
    CONTACTS_CONTAINER,
    CONTACTS_INDEXING_POLICY,
    EDUCATIONS_CONTAINER,
    EVENTS_CONTAINER,
    EVENTS_INDEXING_POLICY,
    EVENTS_PARTITION_KEY,
    EXPERIENCES_CONTAINER,
    RESUMES_CONTAINER,
    RESUMES_INDEXING_POLICY,
    RESUMES_PARTITION_KEY,
    SELECTIONS_CONTAINER,
    SELECTIONS_INDEXING_POLICY,
    SELECTIONS_PARTITION_KEY,
    SKILLS_CONTAINER,
    VERSIONS_CONTAINER,
    VERSIONS_INDEXING_POLICY,
    VERSIONS_PARTITION_KEY,
)

if TYPE_CHECKING:  # pragma: no cover
    from azure.cosmos import DatabaseProxy


def container_specs() -> list[dict[str, Any]]:
    """Return Resume Management containers and their Cosmos policies."""
    children = [
        {
            "id": name,
            "partition_key": CHILDREN_PARTITION_KEY,
            "indexing_policy": CONTACTS_INDEXING_POLICY if name == CONTACTS_CONTAINER else CHILDREN_INDEXING_POLICY,
        }
        for name in (CONTACTS_CONTAINER, SKILLS_CONTAINER, EXPERIENCES_CONTAINER, EDUCATIONS_CONTAINER)
    ]
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
        {
            "id": VERSIONS_CONTAINER,
            "partition_key": VERSIONS_PARTITION_KEY,
            "indexing_policy": VERSIONS_INDEXING_POLICY,
        },
        *children,
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
        if spec["id"] == EVENTS_CONTAINER:
            from app.resumes.constants import PARSED_TTL_SECONDS

            kwargs["default_ttl"] = PARSED_TTL_SECONDS
        database.create_container_if_not_exists(**kwargs)


def ensure_resumes_containers(database: "DatabaseProxy") -> list[str]:
    """Kanban alias: provision resumes, resume_files, resume_parsed (physical + aliases)."""
    ensure_resume_containers(database)
    return ["resumes", "resume_files", "resume_parsed"]

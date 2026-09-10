"""Cosmos container provisioning for Email Ingestion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.mail.constants import (
    ACCOUNTS_CONTAINER,
    ACCOUNT_PK,
    ATTACHMENTS_CONTAINER,
    AUDITS_CONTAINER,
    CURSORS_CONTAINER,
    DRAFTS_CONTAINER,
    EVENTS_CONTAINER,
    MESSAGES_CONTAINER,
    MESSAGES_INDEXING,
    PARTITION_PK,
    RECIPIENTS_CONTAINER,
    SUBSCRIPTIONS_CONTAINER,
    TEMPLATES_CONTAINER,
    THREADS_CONTAINER,
    THREADS_INDEXING,
)

if TYPE_CHECKING:  # pragma: no cover
    from azure.cosmos import DatabaseProxy


def container_specs() -> list[dict[str, Any]]:
    return [
        {"id": ACCOUNTS_CONTAINER, "partition_key": ACCOUNT_PK},
        {"id": THREADS_CONTAINER, "partition_key": PARTITION_PK, "indexing_policy": THREADS_INDEXING},
        {"id": MESSAGES_CONTAINER, "partition_key": PARTITION_PK, "indexing_policy": MESSAGES_INDEXING},
        {"id": RECIPIENTS_CONTAINER, "partition_key": PARTITION_PK},
        {"id": ATTACHMENTS_CONTAINER, "partition_key": PARTITION_PK},
        {"id": DRAFTS_CONTAINER, "partition_key": PARTITION_PK},
        {"id": CURSORS_CONTAINER, "partition_key": PARTITION_PK},
        {"id": SUBSCRIPTIONS_CONTAINER, "partition_key": PARTITION_PK},
        {"id": EVENTS_CONTAINER, "partition_key": PARTITION_PK},
        {"id": AUDITS_CONTAINER, "partition_key": PARTITION_PK},
        {"id": TEMPLATES_CONTAINER, "partition_key": "/id"},
    ]


def ensure_mail_containers(database: "DatabaseProxy") -> None:
    from azure.cosmos import PartitionKey

    for spec in container_specs():
        kwargs: dict[str, Any] = {
            "id": spec["id"],
            "partition_key": PartitionKey(path=spec["partition_key"]),
        }
        if spec.get("indexing_policy"):
            kwargs["indexing_policy"] = spec["indexing_policy"]
        database.create_container_if_not_exists(**kwargs)

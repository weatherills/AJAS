"""Provision Cosmos containers, Blob containers, and Storage Queues."""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.storage.blob_layout import blob_container_names
from app.storage.catalog import container_catalog, cosmos_create_kwargs, ensure_all_containers
from app.storage.queue_schemas import all_queue_names


def provision_cosmos(database: Any | None = None) -> list[str]:
    if database is None:
        from app.storage.cosmos import get_database

        database = get_database()
    return ensure_all_containers(database)


def provision_blobs(service: Any | None = None) -> list[str]:
    if service is None:
        from app.storage.blobs import get_blob_service_client

        service = get_blob_service_client()
    created: list[str] = []
    for name in blob_container_names():
        client = service.get_container_client(name)
        try:
            client.create_container()
        except Exception as exc:  # already exists, or emulator race
            message = str(exc).lower()
            if "already" not in message and "409" not in message and "containerexists" not in message:
                exists = getattr(client, "exists", None)
                if callable(exists) and not exists():
                    raise
        created.append(name)
    return created


def provision_queues(service: Any | None = None) -> list[str]:
    created: list[str] = []
    settings = get_settings()
    if service is None:
        from azure.storage.queue import QueueServiceClient

        if not settings.queue_connection_string:
            raise RuntimeError("QUEUE_CONNECTION_STRING is not configured.")
        service = QueueServiceClient.from_connection_string(settings.queue_connection_string)
    for name in all_queue_names():
        try:
            service.create_queue(name)
        except Exception as exc:
            message = str(exc).lower()
            if "already" not in message and "409" not in message and "queuealreadyexists" not in message:
                client = service.get_queue_client(name)
                exists = getattr(client, "exists", None)
                if callable(exists) and not exists():
                    raise
        created.append(name)
    return created


def provision_all(*, cosmos: bool = True, blobs: bool = True, queues: bool = True, dry_run: bool = False) -> dict[str, Any]:
    plan = {
        "cosmos": [spec.id for spec in container_catalog()] if cosmos else [],
        "blobs": list(blob_container_names()) if blobs else [],
        "queues": list(all_queue_names()) if queues else [],
        "dry_run": dry_run,
    }
    if dry_run:
        plan["status"] = "planned"
        plan["connection"] = connection_info()
        return plan
    created: dict[str, Any] = {"dry_run": False, "status": "provisioned"}
    if cosmos:
        created["cosmos"] = provision_cosmos()
    if blobs:
        created["blobs"] = provision_blobs()
    if queues:
        created["queues"] = provision_queues()
    created["connection"] = connection_info()
    return created


def connection_info() -> dict[str, str]:
    """Env values Functions should receive after provisioning."""
    settings = get_settings()
    return {
        "COSMOS_CONNECTION_STRING": _present(settings.cosmos_connection_string),
        "COSMOS_DATABASE": settings.cosmos_database,
        "BLOB_CONNECTION_STRING": _present(settings.blob_connection_string),
        "QUEUE_CONNECTION_STRING": _present(settings.queue_connection_string),
        "COSMOS_CONTAINERS": str(len(container_catalog())),
        "BLOB_CONTAINERS": ",".join(blob_container_names()),
        "QUEUE_NAMES": ",".join(all_queue_names()),
    }


def _present(value: str) -> str:
    return "set" if (value or "").strip() else "missing"


def cosmos_kwargs_preview() -> list[dict[str, Any]]:
    """JSON-serializable view of create_container kwargs (no SDK objects)."""
    rows = []
    for spec in container_catalog():
        kwargs = cosmos_create_kwargs(spec)
        pk = kwargs["partition_key"]
        rows.append(
            {
                "id": kwargs["id"],
                "partition_key": getattr(pk, "path", None) or spec.partition_key,
                "unique_key_policy": kwargs.get("unique_key_policy"),
                "default_ttl": kwargs.get("default_ttl"),
                "composite_count": len((kwargs.get("indexing_policy") or {}).get("compositeIndexes") or []),
            }
        )
    return rows


def dumps_plan() -> str:
    return json.dumps(provision_all(dry_run=True), indent=2, default=str)

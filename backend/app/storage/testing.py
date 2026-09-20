"""In-memory Cosmos / Blob stand-ins for unit tests (no emulator required)."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from app.storage.dal import ConflictError


def _etag_of(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:16]


class FakeQueryResult(list):
    def __init__(self, items: list[dict[str, Any]], *, continuation: str | None = None, charge: float = 1.0) -> None:
        super().__init__(items)
        self.continuation_token = continuation
        self.headers = {"x-ms-request-charge": str(charge)}


class FakeItemResult(dict):
    def __init__(self, body: dict[str, Any], *, charge: float = 1.0) -> None:
        super().__init__(body)
        self.headers = {"x-ms-request-charge": str(charge)}


class FakeScripts:
    def __init__(self) -> None:
        self.sprocs: dict[str, dict[str, Any]] = {}
        self.udfs: dict[str, dict[str, Any]] = {}
        self.triggers: dict[str, dict[str, Any]] = {}

    def create_stored_procedure(self, body: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        payload = dict(body or kwargs.get("body") or {})
        if payload["id"] in self.sprocs:
            raise ValueError(f"sproc exists {payload['id']}")
        self.sprocs[payload["id"]] = payload
        return payload

    def upsert_stored_procedure(self, body: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        payload = dict(body or kwargs.get("body") or {})
        self.sprocs[payload["id"]] = payload
        return payload

    def create_user_defined_function(self, body: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        payload = dict(body or kwargs.get("body") or {})
        self.udfs[payload["id"]] = payload
        return payload

    def upsert_user_defined_function(self, body: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        payload = dict(body or kwargs.get("body") or {})
        self.udfs[payload["id"]] = payload
        return payload

    def create_trigger(self, body: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        payload = dict(body or kwargs.get("body") or {})
        self.triggers[payload["id"]] = payload
        return payload

    def upsert_trigger(self, body: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        payload = dict(body or kwargs.get("body") or {})
        self.triggers[payload["id"]] = payload
        return payload


class FakeContainer:
    def __init__(self, pk_field: str) -> None:
        self.pk_field = pk_field.lstrip("/")
        self.items: dict[tuple[str, str], dict[str, Any]] = {}
        self.scripts = FakeScripts()

    def create_item(self, body: dict[str, Any] | None = None, **kwargs: Any) -> FakeItemResult:
        payload = dict(body or kwargs.get("body") or {})
        key = (str(payload.get(self.pk_field) or payload.get("id")), str(payload["id"]))
        if key in self.items:
            raise ValueError(f"conflict {key}")
        stored = dict(payload)
        stored["_etag"] = _etag_of(stored)
        self.items[key] = stored
        return FakeItemResult(stored)

    def upsert_item(self, body: dict[str, Any] | None = None, **kwargs: Any) -> FakeItemResult:
        payload = dict(body or kwargs.get("body") or {})
        key = (str(payload.get(self.pk_field) or payload.get("id")), str(payload["id"]))
        stored = dict(payload)
        stored["_etag"] = _etag_of(stored)
        self.items[key] = stored
        return FakeItemResult(stored)

    def replace_item(self, item: str, body: dict[str, Any] | None = None, **kwargs: Any) -> FakeItemResult:
        payload = dict(body or {})
        pk = str(payload.get(self.pk_field) or payload.get("id"))
        key = (pk, item if isinstance(item, str) else payload["id"])
        if key not in self.items:
            raise KeyError(item)
        expected = kwargs.get("etag") or kwargs.get("if_match")
        if expected and self.items[key].get("_etag") != expected:
            raise ConflictError(f"etag mismatch for {item}")
        stored = dict(payload)
        stored["_etag"] = _etag_of(stored)
        self.items[key] = stored
        return FakeItemResult(stored)

    def read_item(self, item: str, partition_key: Any, **kwargs: Any) -> FakeItemResult:
        key = (str(partition_key), str(item))
        if key not in self.items:
            raise KeyError(item)
        return FakeItemResult(self.items[key])

    def delete_item(self, item: str, partition_key: Any, **kwargs: Any) -> FakeItemResult:
        key = (str(partition_key), str(item))
        if key not in self.items:
            raise KeyError(item)
        del self.items[key]
        return FakeItemResult({"id": item})

    def query_items(self, query: str, **kwargs: Any) -> FakeQueryResult:
        rows = [dict(value) for value in self.items.values()]
        pk = kwargs.get("partition_key")
        if pk is not None:
            rows = [row for row in rows if str(row.get(self.pk_field)) == str(pk)]
        continuation = kwargs.get("continuation")
        offset = 0
        if isinstance(continuation, str) and continuation.startswith("offset:"):
            offset = int(continuation.split(":", 1)[1])
        size = int(kwargs.get("max_item_count") or len(rows) or 25)
        window = rows[offset : offset + size]
        token = f"offset:{offset + size}" if offset + size < len(rows) else None
        return FakeQueryResult(window, continuation=token, charge=2.0)


def _pk_for_container(name: str) -> str:
    try:
        from app.storage.catalog import container_by_id

        return container_by_id(name).partition_key.lstrip("/")
    except Exception:
        if name in {"users", "job_postings_canonical", "email_templates", "job_sources", "schema_migrations"}:
            return "id"
        if name in {"email_threads", "email_messages"}:
            return "email_account_id"
        return "user_id"


class FakeDatabase:
    def __init__(self) -> None:
        self._containers: dict[str, FakeContainer] = {}
        self.created: list[dict[str, Any]] = []

    def get_container_client(self, name: str) -> FakeContainer:
        if name not in self._containers:
            self._containers[name] = FakeContainer(_pk_for_container(name))
        return self._containers[name]

    def create_container_if_not_exists(self, **kwargs: Any) -> None:
        self.created.append(kwargs)
        name = kwargs["id"]
        path = kwargs.get("partition_key")
        pk = getattr(path, "path", None) or (path if isinstance(path, str) else "/user_id")
        self._containers[name] = FakeContainer(str(pk))


class MemoryDocumentStore:
    """GDPR/retention test double."""

    def __init__(self) -> None:
        self.docs: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.blobs: dict[str, dict[str, bytes]] = defaultdict(dict)
        self.events: list[dict[str, Any]] = []

    def list_user_documents(self, container: str, user_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.docs[container] if row.get("user_id") == user_id or row.get("id") == user_id]

    def delete_document(self, container: str, item_id: str, partition_key: Any) -> None:
        self.docs[container] = [
            row
            for row in self.docs[container]
            if not (str(row.get("id")) == str(item_id) and str(row.get("user_id") or row.get("id")) == str(partition_key))
        ]

    def write_event(self, body: dict[str, Any]) -> None:
        self.events.append(dict(body))
        self.docs["event_log"].append(dict(body))

    def delete_blobs(self, container: str, prefix: str) -> int:
        victims = [key for key in self.blobs[container] if key.startswith(prefix)]
        for key in victims:
            del self.blobs[container][key]
        return len(victims)

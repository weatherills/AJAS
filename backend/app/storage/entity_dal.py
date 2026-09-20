"""Typed Cosmos repositories for core entities and every catalog container."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.storage.catalog import ContainerSpec, container_catalog, container_by_id
from app.storage.dal import CosmosDAL, Page
from app.storage.entities import Application, EventLog, JobPosting, MailThread, StoredResume, User
from app.storage.sprocs import apply_timestamps, enqueue_hint_for, safe_upsert_document

T = TypeVar("T", bound=BaseModel)

SOFT_DELETE_CONTAINERS = frozenset({"users", "resumes", "email_accounts", "user_settings"})


class StoredDocument(BaseModel):
    """Generic document used by catalog-wide CRUD shims."""

    model_config = ConfigDict(extra="allow")

    id: str
    schemaVersion: int = 1
    is_deleted: bool = False
    deleted_at: str | None = None
    etag: str | None = Field(default=None, alias="_etag")


class EntityRepository(Generic[T]):
    def __init__(self, dal: CosmosDAL, *, container: str, model: type[T], pk_field: str) -> None:
        self._dal = dal
        self.container = container
        self.model = model
        self.pk_field = pk_field

    def create(self, row: T) -> T:
        payload = self._dal.create(self.container, row.model_dump())
        return self.model.model_validate(payload)

    def upsert(self, row: T) -> T:
        payload = self._dal.upsert(self.container, row.model_dump())
        return self.model.model_validate(payload)

    def get(self, item_id: str, *, partition_key: Any) -> T:
        return self.model.model_validate(self._dal.read(self.container, item_id, partition_key=partition_key))

    def delete(self, item_id: str, *, partition_key: Any) -> None:
        self._dal.delete(self.container, item_id, partition_key=partition_key)

    def list_partition(self, partition_key: Any, *, continuation: str | None = None, max_items: int = 25) -> Page:
        page = self._dal.query(
            self.container,
            "SELECT * FROM c",
            partition_key=partition_key,
            continuation=continuation,
            max_items=max_items,
        )
        return Page(
            items=[self.model.model_validate(item).model_dump() for item in page.items],
            continuation=page.continuation,
            request_charge=page.request_charge,
        )


class CatalogRepository:
    """CRUD + optimistic concurrency + optional soft-delete for one catalog container."""

    def __init__(self, dal: CosmosDAL, spec: ContainerSpec) -> None:
        self._dal = dal
        self.spec = spec
        self.container = spec.id
        self.pk_field = spec.partition_key.lstrip("/")

    def _pk(self, row: dict[str, Any]) -> Any:
        return row.get(self.pk_field) or row.get("id")

    def create(self, row: dict[str, Any]) -> dict[str, Any]:
        payload = apply_timestamps(dict(row))
        created = self._dal.create(self.container, payload)
        hint = enqueue_hint_for(self.container, created)
        if hint:
            created["_enqueue"] = hint
        return created

    def upsert(self, row: dict[str, Any], *, etag: str | None = None) -> dict[str, Any]:
        incoming = dict(row)
        existing = None
        item_id = str(incoming.get("id") or "")
        if item_id:
            try:
                existing = self._dal.read(self.container, item_id, partition_key=self._pk(incoming))
            except KeyError:
                existing = None
        merged = safe_upsert_document(existing, incoming)
        if existing and etag:
            return self._dal.replace(self.container, item_id, merged, etag=etag)
        return self._dal.upsert(self.container, merged)

    def get(self, item_id: str, *, partition_key: Any) -> dict[str, Any]:
        return self._dal.read(self.container, item_id, partition_key=partition_key)

    def delete(self, item_id: str, *, partition_key: Any) -> None:
        self._dal.delete(self.container, item_id, partition_key=partition_key)

    def soft_delete(self, item_id: str, *, partition_key: Any) -> dict[str, Any]:
        row = self.get(item_id, partition_key=partition_key)
        row["is_deleted"] = True
        row["deleted_at"] = datetime.now(timezone.utc).isoformat()
        return self._dal.replace(self.container, item_id, row, etag=row.get("_etag") or row.get("etag"))

    def list_partition(self, partition_key: Any, *, continuation: str | None = None, max_items: int = 25) -> Page:
        return self._dal.query(
            self.container,
            "SELECT * FROM c",
            partition_key=partition_key,
            continuation=continuation,
            max_items=max_items,
        )


def core_repositories(dal: CosmosDAL) -> dict[str, EntityRepository[Any]]:
    return {
        "users": EntityRepository(dal, container="users", model=User, pk_field="id"),
        "job_postings_canonical": EntityRepository(
            dal, container="job_postings_canonical", model=JobPosting, pk_field="id"
        ),
        "resumes": EntityRepository(dal, container="resumes", model=StoredResume, pk_field="user_id"),
        "auto_apply_attempts": EntityRepository(
            dal, container="auto_apply_attempts", model=Application, pk_field="user_id"
        ),
        "email_threads": EntityRepository(dal, container="email_threads", model=MailThread, pk_field="email_account_id"),
        "event_log": EntityRepository(dal, container="event_log", model=EventLog, pk_field="user_id"),
    }


def catalog_repositories(dal: CosmosDAL) -> dict[str, CatalogRepository]:
    return {spec.id: CatalogRepository(dal, spec) for spec in container_catalog()}


def repository_for(dal: CosmosDAL, container: str) -> CatalogRepository:
    return CatalogRepository(dal, container_by_id(container))

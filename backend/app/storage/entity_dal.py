"""Typed Cosmos repositories for the six core Database PRD entities."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.storage.dal import CosmosDAL, Page
from app.storage.entities import Application, EventLog, JobPosting, MailThread, StoredResume, User

T = TypeVar("T", bound=BaseModel)


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

"""Cosmos DB implementation of ResumeStore."""

from __future__ import annotations

from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.resumes.constants import (
    EVENTS_CONTAINER,
    RESUMES_CONTAINER,
    SELECTIONS_CONTAINER,
    ChildSource,
    ProcessingStatus,
)
from app.resumes.errors import ResumeNotFoundError
from app.resumes.memory import InMemoryResumeStore
from app.resumes.models import (
    Resume,
    ResumeParseEvent,
    RunResumeSelection,
    StructuredResume,
)


class CosmosResumeStore:
    """Persists resume documents using the same rules as ``InMemoryResumeStore``.

    Mutations go through the in-memory rules (validation, events, uniqueness)
    after loading the caller's current documents from Cosmos, then write back.
    This keeps the Database PRD in one place.
    """

    def __init__(self, database: Any) -> None:
        self._resumes = database.get_container_client(RESUMES_CONTAINER)
        self._events = database.get_container_client(EVENTS_CONTAINER)
        self._selections = database.get_container_client(SELECTIONS_CONTAINER)

    def create_resume(self, **kwargs: Any) -> Resume:
        working = self._hydrate_user(kwargs["user_id"])
        created = working.create_resume(**kwargs)
        self._persist_resume(created)
        self._persist_new_events(working, created.id)
        return created

    def get_resume(self, user_id: str, resume_id: str) -> Resume:
        try:
            item = self._resumes.read_item(item=resume_id, partition_key=user_id)
        except CosmosResourceNotFoundError as exc:
            raise ResumeNotFoundError(resume_id) from exc
        return Resume.model_validate(item)

    def list_resumes(self, user_id: str, *, include_deleted: bool = False) -> list[Resume]:
        query = (
            "SELECT * FROM c WHERE c.user_id = @user_id "
            "AND (@include_deleted = true OR c.is_deleted = false) "
            "ORDER BY c.updated_at DESC"
        )
        items = self._resumes.query_items(
            query=query,
            parameters=[
                {"name": "@user_id", "value": user_id},
                {"name": "@include_deleted", "value": include_deleted},
            ],
            partition_key=user_id,
        )
        return [Resume.model_validate(item) for item in items]

    def record_status(
        self,
        user_id: str,
        resume_id: str,
        status: ProcessingStatus,
        *,
        parsing_error: str | None = None,
    ) -> Resume:
        working = self._hydrate_user(user_id, event_resume_id=resume_id)
        updated = working.record_status(
            user_id, resume_id, status, parsing_error=parsing_error
        )
        self._persist_resume(updated)
        self._persist_new_events(working, resume_id)
        return updated

    def record_parse_success(
        self,
        user_id: str,
        resume_id: str,
        snapshot: StructuredResume,
        *,
        parsing_confidence: int | None = None,
    ) -> Resume:
        working = self._hydrate_user(user_id, event_resume_id=resume_id)
        updated = working.record_parse_success(
            user_id,
            resume_id,
            snapshot,
            parsing_confidence=parsing_confidence,
        )
        self._persist_resume(updated)
        self._persist_new_events(working, resume_id)
        return updated

    def replace_structured_data(
        self,
        user_id: str,
        resume_id: str,
        snapshot: StructuredResume,
        *,
        last_edited_by: str,
        source: ChildSource = "manual",
    ) -> Resume:
        working = self._hydrate_user(user_id, event_resume_id=resume_id)
        updated = working.replace_structured_data(
            user_id,
            resume_id,
            snapshot,
            last_edited_by=last_edited_by,
            source=source,
        )
        self._persist_resume(updated)
        self._persist_new_events(working, resume_id)
        return updated

    def soft_delete(self, user_id: str, resume_id: str) -> Resume:
        working = self._hydrate_user(user_id, event_resume_id=resume_id)
        updated = working.soft_delete(user_id, resume_id)
        self._persist_resume(updated)
        self._persist_new_events(working, resume_id)
        return updated

    def set_run_selection(
        self,
        *,
        run_id: str,
        user_id: str,
        resume_id: str,
    ) -> RunResumeSelection:
        working = self._hydrate_user(user_id)
        existing = self.get_run_selection(run_id)
        if existing is not None:
            working._selections[run_id] = existing  # noqa: SLF001
        selection = working.set_run_selection(
            run_id=run_id, user_id=user_id, resume_id=resume_id
        )
        self._selections.upsert_item(selection.model_dump())
        return selection

    def get_run_selection(self, run_id: str) -> RunResumeSelection | None:
        try:
            item = self._selections.read_item(item=run_id, partition_key=run_id)
        except CosmosResourceNotFoundError:
            return None
        return RunResumeSelection.model_validate(item)

    def list_parse_events(self, resume_id: str) -> list[ResumeParseEvent]:
        query = "SELECT * FROM c WHERE c.resume_id = @resume_id ORDER BY c.created_at DESC"
        items = self._events.query_items(
            query=query,
            parameters=[{"name": "@resume_id", "value": resume_id}],
            partition_key=resume_id,
        )
        return [ResumeParseEvent.model_validate(item) for item in items]

    def _hydrate_user(
        self,
        user_id: str,
        *,
        event_resume_id: str | None = None,
    ) -> InMemoryResumeStore:
        """Load one user's resume docs so in-memory rules can run."""
        working = InMemoryResumeStore()
        query = "SELECT * FROM c WHERE c.user_id = @user_id"
        items = self._resumes.query_items(
            query=query,
            parameters=[{"name": "@user_id", "value": user_id}],
            partition_key=user_id,
        )
        for item in items:
            resume = Resume.model_validate(item)
            working._resumes[(resume.user_id, resume.id)] = resume  # noqa: SLF001
        if event_resume_id:
            working._events[event_resume_id] = self.list_parse_events(event_resume_id)  # noqa: SLF001
        return working

    def _persist_resume(self, resume: Resume) -> None:
        payload = resume.model_dump()
        try:
            self._resumes.replace_item(item=resume.id, body=payload)
        except CosmosResourceNotFoundError:
            self._resumes.create_item(body=payload)

    def _persist_new_events(self, working: InMemoryResumeStore, resume_id: str) -> None:
        existing_ids = {event.id for event in self.list_parse_events(resume_id)}
        for event in working.list_parse_events(resume_id):
            if event.id not in existing_ids:
                self._events.create_item(body=event.model_dump())

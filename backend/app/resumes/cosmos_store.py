"""Cosmos DB implementation of ResumeStore."""

from __future__ import annotations

from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.resumes.children import (
    attach_children,
    child_dumps,
    parent_document,
    snapshot_from_embedded,
    structured_from_rows,
)
from app.resumes.constants import (
    CONTACTS_CONTAINER,
    EDUCATIONS_CONTAINER,
    EVENTS_CONTAINER,
    EXPERIENCES_CONTAINER,
    RESUMES_CONTAINER,
    SELECTIONS_CONTAINER,
    SKILLS_CONTAINER,
    ChildSource,
    ProcessingStatus,
)
from app.resumes.errors import ResumeNotFoundError
from app.resumes.memory import InMemoryResumeStore
from app.resumes.models import (
    Resume,
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
    ResumeParseEvent,
    ResumeSkill,
    RunResumeSelection,
    StructuredResume,
)


class CosmosResumeStore:
    """Persists resume documents using the same rules as ``InMemoryResumeStore``.

    Mutations go through the in-memory rules (validation, events, uniqueness)
    after loading the caller's current documents from Cosmos, then write back.
    Children live in dedicated containers, not as JSON on the parent row.
    """

    def __init__(self, database: Any) -> None:
        self._resumes = database.get_container_client(RESUMES_CONTAINER)
        self._events = database.get_container_client(EVENTS_CONTAINER)
        self._selections = database.get_container_client(SELECTIONS_CONTAINER)
        self._contacts = database.get_container_client(CONTACTS_CONTAINER)
        self._skills = database.get_container_client(SKILLS_CONTAINER)
        self._experiences = database.get_container_client(EXPERIENCES_CONTAINER)
        self._educations = database.get_container_client(EDUCATIONS_CONTAINER)

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
        resume = Resume.model_validate(item)
        snapshot = self._load_children(resume_id, fallback=item)
        return attach_children(resume, snapshot)

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
        rows = []
        for item in items:
            resume = Resume.model_validate(item)
            rows.append(attach_children(resume, self._load_children(resume.id, fallback=item)))
        return rows

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
        source_version: str | None = None,
    ) -> Resume:
        working = self._hydrate_user(user_id, event_resume_id=resume_id)
        updated = working.record_parse_success(
            user_id,
            resume_id,
            snapshot,
            parsing_confidence=parsing_confidence,
            source_version=source_version,
        )
        self._persist_resume(updated)
        self._persist_children(resume_id, working.child_documents(resume_id))
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
        self._persist_children(resume_id, working.child_documents(resume_id))
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

    def clear_selections_for_resume(self, user_id: str, resume_id: str) -> int:
        items = list(
            self._selections.query_items(
                query=(
                    "SELECT * FROM c WHERE c.user_id = @user_id "
                    "AND c.resume_id = @resume_id"
                ),
                parameters=[
                    {"name": "@user_id", "value": user_id},
                    {"name": "@resume_id", "value": resume_id},
                ],
                enable_cross_partition_query=True,
            )
        )
        for item in items:
            self._selections.delete_item(item=item["id"], partition_key=item["run_id"])
        return len(items)

    def set_user_active(self, user_id: str, resume_id: str) -> Resume:
        working = self._hydrate_user(user_id, event_resume_id=resume_id)
        updated = working.set_user_active(user_id, resume_id)
        for resume in working.list_resumes(user_id, include_deleted=True):
            self._persist_resume(resume)
        self._persist_new_events(working, resume_id)
        return updated

    def get_user_active(self, user_id: str) -> Resume | None:
        rows = self.list_resumes(user_id)
        for resume in rows:
            if resume.is_active:
                return resume
        return None

    def list_parse_events(self, resume_id: str) -> list[ResumeParseEvent]:
        query = "SELECT * FROM c WHERE c.resume_id = @resume_id ORDER BY c.created_at DESC"
        items = self._events.query_items(
            query=query,
            parameters=[{"name": "@resume_id", "value": resume_id}],
            partition_key=resume_id,
        )
        return [ResumeParseEvent.model_validate(item) for item in items]

    def child_documents(self, resume_id: str) -> StructuredResume:
        return self._load_children(resume_id)

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
            working._store_parent(resume)  # noqa: SLF001
            snapshot = self._load_children(resume.id, fallback=item)
            working._save_children(resume.id, snapshot)  # noqa: SLF001
        if event_resume_id:
            working._events[event_resume_id] = self.list_parse_events(event_resume_id)  # noqa: SLF001
        return working

    def _persist_resume(self, resume: Resume) -> None:
        payload = parent_document(resume)
        try:
            self._resumes.replace_item(item=resume.id, body=payload)
        except CosmosResourceNotFoundError:
            self._resumes.create_item(body=payload)

    def _persist_children(self, resume_id: str, snapshot: StructuredResume) -> None:
        dumps = child_dumps(snapshot)
        self._replace_rows(self._contacts, resume_id, dumps["contacts"])
        self._replace_rows(self._skills, resume_id, dumps["skills"])
        self._replace_rows(self._experiences, resume_id, dumps["experiences"])
        self._replace_rows(self._educations, resume_id, dumps["educations"])

    def _replace_rows(self, container: Any, resume_id: str, rows: list[dict[str, Any]]) -> None:
        existing = list(
            container.query_items(
                query="SELECT * FROM c WHERE c.resume_id = @resume_id",
                parameters=[{"name": "@resume_id", "value": resume_id}],
                partition_key=resume_id,
            )
        )
        keep = {row["id"] for row in rows}
        for item in existing:
            if item["id"] not in keep:
                container.delete_item(item=item["id"], partition_key=resume_id)
        for row in rows:
            container.upsert_item(row)

    def _load_children(
        self,
        resume_id: str,
        *,
        fallback: dict[str, Any] | None = None,
    ) -> StructuredResume:
        contacts = self._query_children(self._contacts, resume_id)
        skills = self._query_children(self._skills, resume_id, order=True)
        experiences = self._query_children(self._experiences, resume_id, order=True)
        educations = self._query_children(self._educations, resume_id, order=True)
        snapshot = structured_from_rows(
            contacts=[ResumeContact.model_validate(item) for item in contacts],
            skills=[ResumeSkill.model_validate(item) for item in skills],
            experiences=[ResumeExperience.model_validate(item) for item in experiences],
            educations=[ResumeEducation.model_validate(item) for item in educations],
        )
        if (
            snapshot.contact is None
            and not snapshot.skills
            and not snapshot.experiences
            and not snapshot.educations
            and fallback
        ):
            legacy = snapshot_from_embedded(fallback)
            if legacy is not None:
                self._persist_children(resume_id, legacy)
                return legacy
        return snapshot

    def _query_children(self, container: Any, resume_id: str, *, order: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM c WHERE c.resume_id = @resume_id"
        if order:
            query += " ORDER BY c.order_index ASC"
        return list(
            container.query_items(
                query=query,
                parameters=[{"name": "@resume_id", "value": resume_id}],
                partition_key=resume_id,
            )
        )

    def _persist_new_events(self, working: InMemoryResumeStore, resume_id: str) -> None:
        existing_ids = {event.id for event in self.list_parse_events(resume_id)}
        for event in working.list_parse_events(resume_id):
            if event.id not in existing_ids:
                self._events.create_item(body=event.model_dump())

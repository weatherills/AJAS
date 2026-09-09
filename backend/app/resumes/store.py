"""Resume store protocol and factory."""

from __future__ import annotations

from typing import Protocol

from app.resumes.constants import ChildSource, ProcessingStatus
from app.resumes.models import (
    Resume,
    ResumeParseEvent,
    RunResumeSelection,
    StructuredResume,
)


class ResumeStore(Protocol):
    """Persistence for resume documents, parse events, and per-run selections."""

    def create_resume(
        self,
        *,
        user_id: str,
        original_filename: str,
        mime_type: str,
        file_size: int,
        blob_uri: str,
        checksum_sha256: str,
        preview_blob_uri: str | None = None,
        text_preview: str | None = None,
        resume_id: str | None = None,
    ) -> Resume: ...

    def get_resume(self, user_id: str, resume_id: str) -> Resume: ...

    def list_resumes(
        self,
        user_id: str,
        *,
        include_deleted: bool = False,
    ) -> list[Resume]: ...

    def record_status(
        self,
        user_id: str,
        resume_id: str,
        status: ProcessingStatus,
        *,
        parsing_error: str | None = None,
    ) -> Resume: ...

    def record_parse_success(
        self,
        user_id: str,
        resume_id: str,
        snapshot: StructuredResume,
        *,
        parsing_confidence: int | None = None,
    ) -> Resume: ...

    def replace_structured_data(
        self,
        user_id: str,
        resume_id: str,
        snapshot: StructuredResume,
        *,
        last_edited_by: str,
        source: ChildSource = "manual",
    ) -> Resume: ...

    def soft_delete(self, user_id: str, resume_id: str) -> Resume: ...

    def set_run_selection(
        self,
        *,
        run_id: str,
        user_id: str,
        resume_id: str,
    ) -> RunResumeSelection: ...

    def get_run_selection(self, run_id: str) -> RunResumeSelection | None: ...

    def list_parse_events(self, resume_id: str) -> list[ResumeParseEvent]: ...

    def clear_selections_for_resume(self, user_id: str, resume_id: str) -> int: ...


_store: ResumeStore | None = None


def get_resume_store() -> ResumeStore:
    """Return Cosmos when configured, otherwise a process-wide in-memory store."""
    global _store
    if _store is not None:
        return _store
    from app.config import get_settings
    from app.resumes.memory import InMemoryResumeStore

    settings = get_settings()
    if not settings.cosmos_connection_string:
        _store = InMemoryResumeStore()
        return _store
    from app.resumes.cosmos_store import CosmosResumeStore
    from app.storage.cosmos import get_database

    _store = CosmosResumeStore(get_database())
    return _store

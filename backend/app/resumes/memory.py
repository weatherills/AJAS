"""In-memory ResumeStore used by tests and local work without Cosmos."""

from __future__ import annotations

from copy import deepcopy

from app.resumes.children import (
    attach_children,
    empty_children,
    stamp_children,
    structured_from_rows,
)
from app.resumes.constants import CANONICAL_SCHEMA_VERSION, ChildSource, ProcessingStatus
from app.resumes.errors import (
    ResumeNotFoundError,
    ResumeSelectionRejectedError,
    ResumeValidationError,
)
from app.resumes.models import (
    Resume,
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
    ResumeParseEvent,
    ResumeSkill,
    RunResumeSelection,
    StructuredResume,
    new_id,
)
from app.resumes.validation import (
    compute_validated,
    utc_now,
    validate_file_metadata,
    validate_processing_status,
    validate_structured,
)


class InMemoryResumeStore:
    """Reference implementation of the Database PRD behaviors."""

    def __init__(self) -> None:
        self._resumes: dict[tuple[str, str], Resume] = {}
        self._events: dict[str, list[ResumeParseEvent]] = {}
        self._selections: dict[str, RunResumeSelection] = {}
        self._contacts: dict[str, ResumeContact] = {}
        self._skills: dict[str, list[ResumeSkill]] = {}
        self._experiences: dict[str, list[ResumeExperience]] = {}
        self._educations: dict[str, list[ResumeEducation]] = {}

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
    ) -> Resume:
        if not user_id:
            raise ResumeValidationError("user_id is required", path="user_id")
        validate_file_metadata(mime_type=mime_type, file_size=file_size)
        now = utc_now()
        resume = Resume(
            id=resume_id or new_id(),
            user_id=user_id,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size=file_size,
            blob_uri=blob_uri,
            preview_blob_uri=preview_blob_uri,
            text_preview=text_preview,
            checksum_sha256=checksum_sha256,
            processing_status="uploaded",
            schema_version=CANONICAL_SCHEMA_VERSION,
            parsed_version=0,
            is_active=False,
            created_at=now,
            updated_at=now,
        )
        self._store_parent(resume)
        self._append_event(resume, "uploaded", {"filename": original_filename})
        duplicate = self._find_duplicate(user_id, checksum_sha256, resume.id)
        if duplicate is not None:
            self._append_event(
                resume,
                "duplicate_detected",
                {"existing_resume_id": duplicate.id, "checksum_sha256": checksum_sha256},
            )
        return self._hydrate(resume)

    def get_resume(self, user_id: str, resume_id: str) -> Resume:
        resume = self._resumes.get((user_id, resume_id))
        if resume is None:
            raise ResumeNotFoundError(resume_id)
        return self._hydrate(resume)

    def list_resumes(self, user_id: str, *, include_deleted: bool = False) -> list[Resume]:
        rows = [r for (uid, _), r in self._resumes.items() if uid == user_id]
        if not include_deleted:
            rows = [r for r in rows if not r.is_deleted]
        rows.sort(key=lambda r: r.updated_at, reverse=True)
        return [self._hydrate(r) for r in rows]

    def record_status(
        self,
        user_id: str,
        resume_id: str,
        status: ProcessingStatus,
        *,
        parsing_error: str | None = None,
    ) -> Resume:
        validate_processing_status(status)
        resume = self._require(user_id, resume_id)
        now = utc_now()
        resume.processing_status = status
        resume.updated_at = now
        if status == "failed":
            resume.parsing_error = parsing_error
        else:
            resume.parsing_error = None
        if status == "parsed":
            resume.parsed_at = now
        event = {
            "queued": "queued",
            "parsing": "started",
            "parsed": "succeeded",
            "failed": "failed",
            "uploaded": "uploaded",
        }[status]
        detail: dict = {}
        if parsing_error:
            detail["parsing_error"] = parsing_error
        self._store_parent(resume)
        self._append_event(resume, event, detail)  # type: ignore[arg-type]
        return self._hydrate(resume)

    def record_parse_success(
        self,
        user_id: str,
        resume_id: str,
        snapshot: StructuredResume,
        *,
        parsing_confidence: int | None = None,
        source_version: str | None = None,
    ) -> Resume:
        resume = self._require(user_id, resume_id)
        stamped = stamp_children(
            snapshot,
            resume_id=resume.id,
            source="parsed",
            parsing_confidence=parsing_confidence,
            user_id=user_id,
        )
        validate_structured(stamped)
        now = utc_now()
        self._save_children(resume.id, stamped)
        resume.processing_status = "parsed"
        resume.parsed_at = now
        resume.parsing_error = None
        resume.updated_at = now
        resume.schema_version = CANONICAL_SCHEMA_VERSION
        resume.parsed_version = int(resume.parsed_version or 0) + 1
        if source_version:
            resume.source_version = source_version
        _apply_validated(resume, stamped, now)
        self._store_parent(resume)
        self._append_event(
            resume,
            "succeeded",
            {
                "validated": resume.validated,
                "parsing_confidence": parsing_confidence,
                "schemaVersion": resume.schema_version,
                "parsedVersion": resume.parsed_version,
                "sourceVersion": resume.source_version,
            },
        )
        return self._hydrate(resume)

    def replace_structured_data(
        self,
        user_id: str,
        resume_id: str,
        snapshot: StructuredResume,
        *,
        last_edited_by: str,
        source: ChildSource = "manual",
    ) -> Resume:
        resume = self._require(user_id, resume_id)
        old_values = _field_snapshot(self._hydrate(resume))
        stamped = stamp_children(snapshot, resume_id=resume.id, source=source, user_id=user_id)
        validate_structured(stamped)
        now = utc_now()
        self._save_children(resume.id, stamped)
        resume.last_edited_by = last_edited_by
        resume.updated_at = now
        resume.schema_version = CANONICAL_SCHEMA_VERSION
        resume.parsed_version = int(resume.parsed_version or 0) + 1
        _apply_validated(resume, stamped, now)
        self._store_parent(resume)
        new_values = _field_snapshot(self._hydrate(resume))
        self._append_event(
            resume,
            "edited",
            {
                "validated": resume.validated,
                "editor": last_edited_by,
                "old": old_values,
                "new": new_values,
                "parsedVersion": resume.parsed_version,
            },
        )
        return self._hydrate(resume)

    def soft_delete(self, user_id: str, resume_id: str) -> Resume:
        resume = self._require(user_id, resume_id)
        if resume.is_deleted:
            return self._hydrate(resume)
        now = utc_now()
        resume.is_deleted = True
        resume.is_active = False
        resume.deleted_at = now
        resume.updated_at = now
        self._store_parent(resume)
        self._append_event(resume, "deleted", {})
        return self._hydrate(resume)

    def set_user_active(self, user_id: str, resume_id: str) -> Resume:
        target = self._require(user_id, resume_id)
        if target.is_deleted:
            raise ResumeSelectionRejectedError("cannot select a deleted resume")
        now = utc_now()
        for resume in self._resumes.values():
            if resume.user_id != user_id:
                continue
            resume.is_active = resume.id == resume_id
            resume.updated_at = now
            self._store_parent(resume)
        target.is_active = True
        target.updated_at = now
        self._store_parent(target)
        self._append_event(target, "activated", {"editor": user_id, "active": True})
        return self._hydrate(target)

    def get_user_active(self, user_id: str) -> Resume | None:
        for resume in self.list_resumes(user_id):
            if resume.is_active:
                return resume
        return None

    def set_run_selection(
        self,
        *,
        run_id: str,
        user_id: str,
        resume_id: str,
    ) -> RunResumeSelection:
        resume = self._require(user_id, resume_id)
        if resume.user_id != user_id:
            raise ResumeSelectionRejectedError("run user_id must match resume user_id")
        if resume.is_deleted:
            raise ResumeSelectionRejectedError("cannot select a deleted resume")
        if resume.processing_status != "parsed":
            raise ResumeSelectionRejectedError("cannot select a resume that is not parsed")
        selection = RunResumeSelection(
            id=run_id,
            run_id=run_id,
            user_id=user_id,
            resume_id=resume_id,
            created_at=utc_now(),
        )
        self._selections[run_id] = selection
        return deepcopy(selection)

    def get_run_selection(self, run_id: str) -> RunResumeSelection | None:
        selection = self._selections.get(run_id)
        return deepcopy(selection) if selection else None

    def clear_selections_for_resume(self, user_id: str, resume_id: str) -> int:
        """Remove per-run selections pointing at this resume (Backend PRD revoke)."""
        to_drop = [
            run_id
            for run_id, sel in self._selections.items()
            if sel.user_id == user_id and sel.resume_id == resume_id
        ]
        for run_id in to_drop:
            del self._selections[run_id]
        return len(to_drop)

    def list_parse_events(self, resume_id: str) -> list[ResumeParseEvent]:
        events = list(self._events.get(resume_id, []))
        indexed = list(enumerate(events))
        indexed.sort(key=lambda pair: (pair[1].created_at, pair[0]), reverse=True)
        return [deepcopy(event) for _, event in indexed]

    def child_documents(self, resume_id: str) -> StructuredResume:
        """Return child rows stored off the parent document."""
        return self._children(resume_id)

    def _require(self, user_id: str, resume_id: str) -> Resume:
        resume = self._resumes.get((user_id, resume_id))
        if resume is None:
            raise ResumeNotFoundError(resume_id)
        return resume

    def _find_duplicate(
        self,
        user_id: str,
        checksum: str,
        exclude_id: str,
    ) -> Resume | None:
        for (uid, rid), resume in self._resumes.items():
            if uid == user_id and rid != exclude_id and resume.checksum_sha256 == checksum:
                return resume
        return None

    def _append_event(self, resume: Resume, event_type: str, detail: dict) -> None:
        event = ResumeParseEvent(
            resume_id=resume.id,
            user_id=resume.user_id,
            event_type=event_type,  # type: ignore[arg-type]
            detail=detail,
            created_at=utc_now(),
        )
        self._events.setdefault(resume.id, []).append(event)

    def _children(self, resume_id: str) -> StructuredResume:
        contact = self._contacts.get(resume_id)
        return structured_from_rows(
            contacts=[contact] if contact is not None else [],
            skills=self._skills.get(resume_id, []),
            experiences=self._experiences.get(resume_id, []),
            educations=self._educations.get(resume_id, []),
        )

    def _save_children(self, resume_id: str, snapshot: StructuredResume) -> None:
        if snapshot.contact is None:
            self._contacts.pop(resume_id, None)
        else:
            self._contacts[resume_id] = snapshot.contact
        self._skills[resume_id] = list(snapshot.skills)
        self._experiences[resume_id] = list(snapshot.experiences)
        self._educations[resume_id] = list(snapshot.educations)

    def _store_parent(self, resume: Resume) -> None:
        self._resumes[(resume.user_id, resume.id)] = attach_children(resume, empty_children())

    def _hydrate(self, resume: Resume) -> Resume:
        return deepcopy(attach_children(resume, self._children(resume.id)))


def _field_snapshot(resume: Resume) -> dict:
    return {
        "skills": [skill.name for skill in resume.skills],
        "experience": [
            {"title": item.title, "company": item.company, "startDate": item.start_date, "endDate": item.end_date}
            for item in resume.experiences
        ],
        "education": [
            {"institution": item.institution, "degree": item.degree}
            for item in resume.educations
        ],
        "contact": (
            {
                "fullName": resume.contact.full_name,
                "email": resume.contact.email,
                "phone": resume.contact.phone,
            }
            if resume.contact
            else None
        ),
    }


def _apply_validated(resume: Resume, snapshot: StructuredResume, now: str) -> None:
    if compute_validated(snapshot):
        resume.validated = True
        resume.validated_at = now
    else:
        resume.validated = False
        resume.validated_at = None

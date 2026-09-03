"""In-memory ResumeStore used by tests and local work without Cosmos."""

from __future__ import annotations

from copy import deepcopy

from app.resumes.constants import ChildSource, ProcessingStatus
from app.resumes.errors import (
    ResumeNotFoundError,
    ResumeSelectionRejectedError,
    ResumeValidationError,
)
from app.resumes.models import (
    Resume,
    ResumeParseEvent,
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
    ) -> Resume:
        if not user_id:
            raise ResumeValidationError("user_id is required", path="user_id")
        validate_file_metadata(mime_type=mime_type, file_size=file_size)
        now = utc_now()
        resume = Resume(
            user_id=user_id,
            original_filename=original_filename,
            mime_type=mime_type,
            file_size=file_size,
            blob_uri=blob_uri,
            preview_blob_uri=preview_blob_uri,
            text_preview=text_preview,
            checksum_sha256=checksum_sha256,
            processing_status="uploaded",
            created_at=now,
            updated_at=now,
        )
        self._resumes[(user_id, resume.id)] = resume
        self._append_event(resume, "uploaded", {"filename": original_filename})
        duplicate = self._find_duplicate(user_id, checksum_sha256, resume.id)
        if duplicate is not None:
            self._append_event(
                resume,
                "duplicate_detected",
                {"existing_resume_id": duplicate.id, "checksum_sha256": checksum_sha256},
            )
        return deepcopy(resume)

    def get_resume(self, user_id: str, resume_id: str) -> Resume:
        resume = self._resumes.get((user_id, resume_id))
        if resume is None:
            raise ResumeNotFoundError(resume_id)
        return deepcopy(resume)

    def list_resumes(self, user_id: str, *, include_deleted: bool = False) -> list[Resume]:
        rows = [r for (uid, _), r in self._resumes.items() if uid == user_id]
        if not include_deleted:
            rows = [r for r in rows if not r.is_deleted]
        rows.sort(key=lambda r: r.updated_at, reverse=True)
        return [deepcopy(r) for r in rows]

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
        elif status == "parsed":
            resume.parsed_at = now
            resume.parsing_error = None
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
        self._append_event(resume, event, detail)  # type: ignore[arg-type]
        return deepcopy(resume)

    def record_parse_success(
        self,
        user_id: str,
        resume_id: str,
        snapshot: StructuredResume,
        *,
        parsing_confidence: int | None = None,
    ) -> Resume:
        resume = self._require(user_id, resume_id)
        stamped = _stamp_children(
            snapshot,
            resume_id=resume.id,
            source="parsed",
            parsing_confidence=parsing_confidence,
        )
        validate_structured(stamped)
        now = utc_now()
        resume.contact = stamped.contact
        resume.skills = stamped.skills
        resume.experiences = stamped.experiences
        resume.educations = stamped.educations
        resume.processing_status = "parsed"
        resume.parsed_at = now
        resume.parsing_error = None
        resume.updated_at = now
        _apply_validated(resume, stamped, now)
        self._append_event(
            resume,
            "succeeded",
            {"validated": resume.validated, "parsing_confidence": parsing_confidence},
        )
        return deepcopy(resume)

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
        stamped = _stamp_children(snapshot, resume_id=resume.id, source=source)
        validate_structured(stamped)
        now = utc_now()
        resume.contact = stamped.contact
        resume.skills = stamped.skills
        resume.experiences = stamped.experiences
        resume.educations = stamped.educations
        resume.last_edited_by = last_edited_by
        resume.updated_at = now
        _apply_validated(resume, stamped, now)
        self._append_event(resume, "edited", {"validated": resume.validated})
        return deepcopy(resume)

    def soft_delete(self, user_id: str, resume_id: str) -> Resume:
        resume = self._require(user_id, resume_id)
        if resume.is_deleted:
            return deepcopy(resume)
        now = utc_now()
        resume.is_deleted = True
        resume.deleted_at = now
        resume.updated_at = now
        self._append_event(resume, "deleted", {})
        return deepcopy(resume)

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
            raise ResumeSelectionRejectedError(
                "cannot select a resume that is not parsed"
            )
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

    def list_parse_events(self, resume_id: str) -> list[ResumeParseEvent]:
        events = list(self._events.get(resume_id, []))
        indexed = list(enumerate(events))
        indexed.sort(key=lambda pair: (pair[1].created_at, pair[0]), reverse=True)
        return [deepcopy(event) for _, event in indexed]

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


def _stamp_children(
    snapshot: StructuredResume,
    *,
    resume_id: str,
    source: ChildSource,
    parsing_confidence: int | None = None,
) -> StructuredResume:
    now = utc_now()
    contact = snapshot.contact
    if contact is not None:
        contact = contact.model_copy(
            update={
                "resume_id": resume_id,
                "source": source,
                "updated_at": now,
                **(
                    {"parsing_confidence": parsing_confidence}
                    if parsing_confidence is not None and source == "parsed"
                    else {}
                ),
            }
        )
    skills = []
    for i, skill in enumerate(snapshot.skills):
        skills.append(
            skill.model_copy(
                update={
                    "resume_id": resume_id,
                    "source": source,
                    "order_index": i,
                    "updated_at": now,
                    **(
                        {"parsing_confidence": parsing_confidence}
                        if parsing_confidence is not None and source == "parsed"
                        else {}
                    ),
                }
            )
        )
    experiences = []
    for i, item in enumerate(snapshot.experiences):
        experiences.append(
            item.model_copy(
                update={
                    "resume_id": resume_id,
                    "source": source,
                    "order_index": i,
                    "updated_at": now,
                    **(
                        {"parsing_confidence": parsing_confidence}
                        if parsing_confidence is not None and source == "parsed"
                        else {}
                    ),
                }
            )
        )
    educations = []
    for i, item in enumerate(snapshot.educations):
        educations.append(
            item.model_copy(
                update={
                    "resume_id": resume_id,
                    "source": source,
                    "order_index": i,
                    "updated_at": now,
                    **(
                        {"parsing_confidence": parsing_confidence}
                        if parsing_confidence is not None and source == "parsed"
                        else {}
                    ),
                }
            )
        )
    return StructuredResume(
        contact=contact,
        skills=skills,
        experiences=experiences,
        educations=educations,
    )


def _apply_validated(resume: Resume, snapshot: StructuredResume, now: str) -> None:
    if compute_validated(snapshot):
        resume.validated = True
        resume.validated_at = now
    else:
        resume.validated = False
        resume.validated_at = None

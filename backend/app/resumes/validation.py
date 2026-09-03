"""Constraint checks from the Resume Management Database PRD."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date

from app.resumes.constants import (
    ALLOWED_MIME_TYPES,
    MAX_DESCRIPTION_LEN,
    MAX_EDUCATIONS,
    MAX_EXPERIENCES,
    MAX_SKILL_LEN,
    MAX_SKILLS,
    MAX_TITLE_LEN,
    PROCESSING_STATUSES,
)
from app.resumes.errors import ResumeValidationError
from app.resumes.models import (
    LibraryPreview,
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeSkill,
    StructuredResume,
)

_DATE_FULL = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_MONTH = re.compile(r"^\d{4}-\d{2}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with a Z suffix."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_resume_date(value: str, *, end: bool = False) -> date:
    """Parse YYYY-MM-DD or YYYY-MM. Month-only end dates use the last day."""
    if _DATE_FULL.fullmatch(value):
        return date.fromisoformat(value)
    if _DATE_MONTH.fullmatch(value):
        year, month = (int(part) for part in value.split("-"))
        day = monthrange(year, month)[1] if end else 1
        return date(year, month, day)
    raise ResumeValidationError(
        f"Date must be YYYY-MM-DD or YYYY-MM, got {value!r}",
        path="date",
    )


def validate_date_range(
    start_date: str | None,
    end_date: str | None,
    *,
    is_current: bool,
    path: str,
) -> None:
    if is_current and end_date is not None:
        raise ResumeValidationError(
            "is_current=true requires end_date to be null",
            path=f"{path}/end_date",
        )
    if start_date:
        parse_resume_date(start_date)
    if end_date:
        parse_resume_date(end_date, end=True)
    if start_date and end_date:
        start = parse_resume_date(start_date)
        finish = parse_resume_date(end_date, end=True)
        if finish < start:
            raise ResumeValidationError(
                "end_date must be >= start_date when both are present",
                path=f"{path}/end_date",
            )


def validate_file_metadata(*, mime_type: str, file_size: int) -> None:
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ResumeValidationError(
            f"mime_type must be PDF or DOCX, got {mime_type!r}",
            path="mime_type",
        )
    if file_size <= 0:
        raise ResumeValidationError("file_size must be > 0", path="file_size")


def validate_processing_status(status: str) -> None:
    if status not in PROCESSING_STATUSES:
        raise ResumeValidationError(
            f"processing_status must be one of {sorted(PROCESSING_STATUSES)}",
            path="processing_status",
        )


def _check_len(value: str | None, max_len: int, path: str) -> None:
    if value is not None and len(value) > max_len:
        raise ResumeValidationError(
            f"{path} exceeds max length {max_len}",
            path=path,
        )


def validate_skill(skill: ResumeSkill, *, index: int) -> None:
    path = f"skills/{index}"
    if not skill.name.strip():
        raise ResumeValidationError("skill name is required", path=f"{path}/name")
    _check_len(skill.name, MAX_SKILL_LEN, f"{path}/name")
    if skill.parsing_confidence is not None and not (0 <= skill.parsing_confidence <= 100):
        raise ResumeValidationError(
            "parsing_confidence must be 0–100",
            path=f"{path}/parsing_confidence",
        )


def validate_experience(item: ResumeExperience, *, index: int) -> None:
    path = f"experiences/{index}"
    _check_len(item.title, MAX_TITLE_LEN, f"{path}/title")
    _check_len(item.company, MAX_TITLE_LEN, f"{path}/company")
    _check_len(item.description, MAX_DESCRIPTION_LEN, f"{path}/description")
    validate_date_range(
        item.start_date,
        item.end_date,
        is_current=item.is_current,
        path=path,
    )
    if item.parsing_confidence is not None and not (0 <= item.parsing_confidence <= 100):
        raise ResumeValidationError(
            "parsing_confidence must be 0–100",
            path=f"{path}/parsing_confidence",
        )


def validate_education(item: ResumeEducation, *, index: int) -> None:
    path = f"educations/{index}"
    _check_len(item.institution, MAX_TITLE_LEN, f"{path}/institution")
    _check_len(item.degree, MAX_TITLE_LEN, f"{path}/degree")
    _check_len(item.field, MAX_TITLE_LEN, f"{path}/field")
    _check_len(item.notes, MAX_DESCRIPTION_LEN, f"{path}/notes")
    validate_date_range(
        item.start_date,
        item.end_date,
        is_current=item.is_current,
        path=path,
    )
    if item.parsing_confidence is not None and not (0 <= item.parsing_confidence <= 100):
        raise ResumeValidationError(
            "parsing_confidence must be 0–100",
            path=f"{path}/parsing_confidence",
        )


def validate_structured(snapshot: StructuredResume) -> None:
    """Raise if child rows violate date, length, or cardinality rules."""
    if snapshot.contact and snapshot.contact.email:
        if not _EMAIL.fullmatch(snapshot.contact.email):
            raise ResumeValidationError("invalid email", path="contact/email")
        if snapshot.contact.parsing_confidence is not None and not (
            0 <= snapshot.contact.parsing_confidence <= 100
        ):
            raise ResumeValidationError(
                "parsing_confidence must be 0–100",
                path="contact/parsing_confidence",
            )

    if len(snapshot.skills) > MAX_SKILLS:
        raise ResumeValidationError(f"skills cannot exceed {MAX_SKILLS}", path="skills")
    if len(snapshot.experiences) > MAX_EXPERIENCES:
        raise ResumeValidationError(
            f"experiences cannot exceed {MAX_EXPERIENCES}",
            path="experiences",
        )
    if len(snapshot.educations) > MAX_EDUCATIONS:
        raise ResumeValidationError(
            f"educations cannot exceed {MAX_EDUCATIONS}",
            path="educations",
        )

    for i, skill in enumerate(snapshot.skills):
        validate_skill(skill, index=i)
    for i, exp in enumerate(snapshot.experiences):
        validate_experience(exp, index=i)
    for i, edu in enumerate(snapshot.educations):
        validate_education(edu, index=i)


def is_structurally_complete(snapshot: StructuredResume) -> bool:
    """Required for ``validated=true``: at least one skill, experience, or education."""
    return bool(snapshot.skills or snapshot.experiences or snapshot.educations)


def compute_validated(snapshot: StructuredResume) -> bool:
    """Return True when child data is complete and passes validation."""
    try:
        validate_structured(snapshot)
    except ResumeValidationError:
        return False
    return is_structurally_complete(snapshot)


def library_preview(resume: Resume) -> LibraryPreview:
    """Library/preview projection. Deleted resumes never expose blob URIs."""
    if resume.is_deleted:
        return LibraryPreview(
            resume_id=resume.id,
            text_preview=resume.text_preview,
            preview_blob_uri=None,
            blob_uri=None,
        )
    return LibraryPreview(
        resume_id=resume.id,
        text_preview=resume.text_preview,
        preview_blob_uri=resume.preview_blob_uri,
        blob_uri=resume.blob_uri,
    )

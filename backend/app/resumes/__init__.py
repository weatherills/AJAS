"""Resume Management database layer (Cosmos schema + store).

This package implements the Database PRD: resume documents, embedded
contact/skills/experience/education children, append-only parse events, and
exactly-one-resume-per-run selections.
"""

from app.resumes.constants import (
    ALLOWED_MIME_TYPES,
    EVENTS_CONTAINER,
    PROCESSING_STATUSES,
    RESUMES_CONTAINER,
    SELECTIONS_CONTAINER,
)
from app.resumes.containers import container_specs, ensure_resume_containers
from app.resumes.errors import (
    ResumeNotFoundError,
    ResumeSelectionRejectedError,
    ResumeStoreError,
    ResumeValidationError,
)
from app.resumes.memory import InMemoryResumeStore
from app.resumes.models import (
    LibraryPreview,
    Resume,
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
    ResumeParseEvent,
    ResumeSkill,
    RunResumeSelection,
    StructuredResume,
)
from app.resumes.store import ResumeStore, get_resume_store
from app.resumes.validation import library_preview

__all__ = [
    "ALLOWED_MIME_TYPES",
    "EVENTS_CONTAINER",
    "PROCESSING_STATUSES",
    "RESUMES_CONTAINER",
    "SELECTIONS_CONTAINER",
    "InMemoryResumeStore",
    "LibraryPreview",
    "Resume",
    "ResumeContact",
    "ResumeEducation",
    "ResumeExperience",
    "ResumeNotFoundError",
    "ResumeParseEvent",
    "ResumeSelectionRejectedError",
    "ResumeSkill",
    "ResumeStore",
    "ResumeStoreError",
    "ResumeValidationError",
    "RunResumeSelection",
    "StructuredResume",
    "container_specs",
    "ensure_resume_containers",
    "get_resume_store",
    "library_preview",
]

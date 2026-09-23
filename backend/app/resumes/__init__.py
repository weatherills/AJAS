"""Resume Management database layer (Cosmos schema + store).

This package implements the Database PRD: resume documents, child containers
for contacts/skills/experiences/educations, append-only parse events, and
exactly-one-resume-per-run selections.
"""

from app.resumes.constants import (
    ALLOWED_MIME_TYPES,
    CHILD_CONTAINERS,
    CONTACTS_CONTAINER,
    EDUCATIONS_CONTAINER,
    EVENTS_CONTAINER,
    EXPERIENCES_CONTAINER,
    PROCESSING_STATUSES,
    RESUMES_CONTAINER,
    SELECTIONS_CONTAINER,
    SKILLS_CONTAINER,
)
from app.resumes.containers import container_specs, ensure_resume_containers, ensure_resumes_containers
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
    "CHILD_CONTAINERS",
    "CONTACTS_CONTAINER",
    "EDUCATIONS_CONTAINER",
    "EVENTS_CONTAINER",
    "EXPERIENCES_CONTAINER",
    "PROCESSING_STATUSES",
    "RESUMES_CONTAINER",
    "SELECTIONS_CONTAINER",
    "SKILLS_CONTAINER",
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
    "ensure_resumes_containers",
    "get_resume_store",
    "library_preview",
]

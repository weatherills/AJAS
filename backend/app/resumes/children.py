"""Helpers that keep parsed children in dedicated Cosmos containers.

The Resume Management Database PRD stores contact/skills/experiences/educations
as child rows, not JSON blobs on the parent ``resumes`` document. The HTTP
layer still sees a hydrated ``Resume`` with nested lists.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.resumes.constants import ChildSource
from app.resumes.models import (
    Resume,
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
    ResumeSkill,
    StructuredResume,
)
from app.resumes.validation import utc_now

PARENT_CHILD_FIELDS: tuple[str, ...] = ("contact", "skills", "experiences", "educations")


def contact_document_id(resume_id: str) -> str:
    """1:1 uniqueness: the contact document id equals the parent resume id."""
    return resume_id


def parent_document(resume: Resume) -> dict[str, Any]:
    """Serialize the parent row without embedded child collections."""
    payload = resume.model_dump()
    for field in PARENT_CHILD_FIELDS:
        payload.pop(field, None)
    return payload


def attach_children(resume: Resume, snapshot: StructuredResume) -> Resume:
    return resume.model_copy(
        update={
            "contact": snapshot.contact,
            "skills": sorted(snapshot.skills, key=lambda item: item.order_index),
            "experiences": sorted(snapshot.experiences, key=lambda item: item.order_index),
            "educations": sorted(snapshot.educations, key=lambda item: item.order_index),
        }
    )


def empty_children() -> StructuredResume:
    return StructuredResume()


def snapshot_from_embedded(item: dict[str, Any]) -> StructuredResume | None:
    """Read legacy parent-embedded children if child containers are empty."""
    if not any(item.get(field) for field in PARENT_CHILD_FIELDS):
        return None
    payload = {field: item.get(field) for field in PARENT_CHILD_FIELDS}
    for field in ("skills", "experiences", "educations"):
        if payload.get(field) is None:
            payload[field] = []
    return StructuredResume.model_validate(payload)


def stamp_children(
    snapshot: StructuredResume,
    *,
    resume_id: str,
    source: ChildSource,
    parsing_confidence: int | None = None,
    user_id: str | None = None,
) -> StructuredResume:
    now = utc_now()

    def extras() -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if parsing_confidence is not None and source == "parsed":
            payload["parsing_confidence"] = parsing_confidence
        if user_id:
            payload["user_id"] = user_id
        return payload

    contact = snapshot.contact
    if contact is not None:
        contact = contact.model_copy(
            update={
                "id": contact_document_id(resume_id),
                "resume_id": resume_id,
                "source": source,
                "updated_at": now,
                **extras(),
            }
        )
    skills = [
        skill.model_copy(
            update={
                "resume_id": resume_id,
                "source": source,
                "order_index": index,
                "updated_at": now,
                **extras(),
            }
        )
        for index, skill in enumerate(snapshot.skills)
    ]
    experiences = [
        item.model_copy(
            update={
                "resume_id": resume_id,
                "source": source,
                "order_index": index,
                "updated_at": now,
                **extras(),
            }
        )
        for index, item in enumerate(snapshot.experiences)
    ]
    educations = [
        item.model_copy(
            update={
                "resume_id": resume_id,
                "source": source,
                "order_index": index,
                "updated_at": now,
                **extras(),
            }
        )
        for index, item in enumerate(snapshot.educations)
    ]
    return StructuredResume(
        contact=contact,
        skills=skills,
        experiences=experiences,
        educations=educations,
    )


def ordered(items: Iterable[Any]) -> list[Any]:
    return sorted(items, key=lambda item: getattr(item, "order_index", 0))


def child_dumps(snapshot: StructuredResume) -> dict[str, list[dict[str, Any]]]:
    skills = [item.model_dump() for item in ordered(snapshot.skills)]
    experiences = [item.model_dump() for item in ordered(snapshot.experiences)]
    educations = [item.model_dump() for item in ordered(snapshot.educations)]
    contacts = [snapshot.contact.model_dump()] if snapshot.contact is not None else []
    return {
        "contacts": contacts,
        "skills": skills,
        "experiences": experiences,
        "educations": educations,
    }


def structured_from_rows(
    *,
    contacts: list[ResumeContact] | list[dict[str, Any]],
    skills: list[ResumeSkill] | list[dict[str, Any]],
    experiences: list[ResumeExperience] | list[dict[str, Any]],
    educations: list[ResumeEducation] | list[dict[str, Any]],
) -> StructuredResume:
    contact_models = [
        item if isinstance(item, ResumeContact) else ResumeContact.model_validate(item)
        for item in contacts
    ]
    skill_models = [
        item if isinstance(item, ResumeSkill) else ResumeSkill.model_validate(item) for item in skills
    ]
    experience_models = [
        item if isinstance(item, ResumeExperience) else ResumeExperience.model_validate(item)
        for item in experiences
    ]
    education_models = [
        item if isinstance(item, ResumeEducation) else ResumeEducation.model_validate(item)
        for item in educations
    ]
    return StructuredResume(
        contact=contact_models[0] if contact_models else None,
        skills=ordered(skill_models),
        experiences=ordered(experience_models),
        educations=ordered(education_models),
    )

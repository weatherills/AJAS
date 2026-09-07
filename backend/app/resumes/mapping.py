"""Map Resume store documents to the Backend PRD HTTP JSON shape."""

from __future__ import annotations

from typing import Any

from app.resumes.models import (
    Resume,
    ResumeEducation,
    ResumeExperience,
    ResumeSkill,
    RunResumeSelection,
    StructuredResume,
)
from app.resumes.validation import utc_now


def api_status(resume: Resume) -> str:
    if resume.is_deleted:
        return "deleted"
    if resume.processing_status == "failed":
        return "parse_failed"
    if resume.processing_status == "queued":
        return "parsing"
    return resume.processing_status


def resume_list_item(resume: Resume) -> dict[str, Any]:
    return {
        "id": resume.id,
        "fileName": resume.original_filename,
        "mimeType": resume.mime_type,
        "size": resume.file_size,
        "status": api_status(resume),
        "createdAt": resume.created_at,
        "updatedAt": resume.updated_at,
        "lastParseAt": resume.parsed_at,
        "fileHash": resume.checksum_sha256,
        "validated": resume.validated,
    }


def resume_detail(resume: Resume) -> dict[str, Any]:
    body = resume_list_item(resume)
    body.update(
        {
            "ownerUserId": resume.user_id,
            "fileHash": resume.checksum_sha256,
            "lastParseError": resume.parsing_error,
            "skills": [skill.name for skill in resume.skills],
            "experience": [_experience_api(item) for item in resume.experiences],
            "education": [_education_api(item) for item in resume.educations],
            "contact": (
                {
                    "fullName": resume.contact.full_name,
                    "email": resume.contact.email,
                    "phone": resume.contact.phone,
                    "location": resume.contact.location,
                    "linkedinUrl": resume.contact.linkedin_url,
                }
                if resume.contact
                else None
            ),
        }
    )
    return body


def _experience_api(item: ResumeExperience) -> dict[str, Any]:
    return {
        "title": item.title,
        "company": item.company,
        "location": item.location,
        "startDate": item.start_date,
        "endDate": item.end_date,
        "isCurrent": item.is_current,
        "description": item.description,
    }


def _education_api(item: ResumeEducation) -> dict[str, Any]:
    return {
        "institution": item.institution,
        "degree": item.degree,
        "field": item.field,
        "startDate": item.start_date,
        "endDate": item.end_date,
        "isCurrent": item.is_current,
        "notes": item.notes,
    }


def snapshot_from_patch(resume: Resume, body: dict[str, Any]) -> StructuredResume:
    """Merge a partial PATCH body onto the current resume children."""
    from app.resumes.models import ResumeContact

    skills = resume.skills
    experiences = resume.experiences
    educations = resume.educations
    contact = resume.contact
    if "skills" in body:
        skills = [_skill_from_api(resume.id, value, i) for i, value in enumerate(body["skills"] or [])]
    if "experience" in body:
        experiences = [
            _experience_from_api(resume.id, value, i) for i, value in enumerate(body["experience"] or [])
        ]
    if "education" in body:
        educations = [
            _education_from_api(resume.id, value, i) for i, value in enumerate(body["education"] or [])
        ]
    if "contact" in body:
        raw = body.get("contact") or {}
        contact = ResumeContact(
            resume_id=resume.id,
            full_name=raw.get("fullName") or raw.get("full_name"),
            email=raw.get("email"),
            phone=raw.get("phone"),
            location=raw.get("location"),
            linkedin_url=raw.get("linkedinUrl") or raw.get("linkedin_url"),
            source="manual",
            updated_at=utc_now(),
        )
    return StructuredResume(
        contact=contact,
        skills=skills,
        experiences=experiences,
        educations=educations,
    )


def snapshot_from_parser(resume_id: str, payload: dict[str, Any]) -> StructuredResume:
    skills = [_skill_from_api(resume_id, value, i) for i, value in enumerate(payload.get("skills") or [])]
    experiences = [
        _experience_from_api(resume_id, value, i)
        for i, value in enumerate(payload.get("experience") or payload.get("experiences") or [])
    ]
    educations = [
        _education_from_api(resume_id, value, i)
        for i, value in enumerate(payload.get("education") or payload.get("educations") or [])
    ]
    contact = None
    raw_contact = payload.get("contact")
    if isinstance(raw_contact, dict):
        from app.resumes.models import ResumeContact

        contact = ResumeContact(
            resume_id=resume_id,
            full_name=raw_contact.get("fullName") or raw_contact.get("full_name"),
            email=raw_contact.get("email"),
            phone=raw_contact.get("phone"),
            location=raw_contact.get("location"),
            linkedin_url=raw_contact.get("linkedinUrl") or raw_contact.get("linkedin_url"),
            updated_at=utc_now(),
        )
    return StructuredResume(
        contact=contact,
        skills=skills,
        experiences=experiences,
        educations=educations,
    )


def _skill_from_api(resume_id: str, value: Any, index: int) -> ResumeSkill:
    name = value if isinstance(value, str) else str((value or {}).get("name") or "")
    return ResumeSkill(
        resume_id=resume_id,
        name=name,
        order_index=index,
        source="manual",
        updated_at=utc_now(),
    )


def _experience_from_api(resume_id: str, value: dict[str, Any], index: int) -> ResumeExperience:
    return ResumeExperience(
        resume_id=resume_id,
        title=value.get("title"),
        company=value.get("company"),
        location=value.get("location"),
        start_date=value.get("startDate") or value.get("start_date"),
        end_date=value.get("endDate") or value.get("end_date"),
        is_current=bool(value.get("isCurrent") or value.get("is_current")),
        description=value.get("description"),
        order_index=index,
        source="manual",
        updated_at=utc_now(),
    )


def _education_from_api(resume_id: str, value: dict[str, Any], index: int) -> ResumeEducation:
    return ResumeEducation(
        resume_id=resume_id,
        institution=value.get("institution") or value.get("school"),
        degree=value.get("degree"),
        field=value.get("field") or value.get("fieldOfStudy"),
        start_date=value.get("startDate") or value.get("start_date"),
        end_date=value.get("endDate") or value.get("end_date"),
        is_current=bool(value.get("isCurrent") or value.get("is_current")),
        notes=value.get("notes"),
        order_index=index,
        source="manual",
        updated_at=utc_now(),
    )


def selection_api(selection: RunResumeSelection) -> dict[str, Any]:
    return {
        "runId": selection.run_id,
        "resumeId": selection.resume_id,
        "effectiveAt": selection.created_at,
    }

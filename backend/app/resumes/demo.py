"""Local demo resume so Review, Jobs, and Apply share a stable resume id."""

from __future__ import annotations

from app.resumes.errors import ResumeNotFoundError
from app.resumes.models import (
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
    ResumeSkill,
    StructuredResume,
)
from app.resumes.validation import utc_now

DEMO_USER = "local-user"
DEMO_RESUME_ID = "resume-1"


def seed_demo_resume(store) -> None:
    """Idempotent parsed resume used by Review demo matches (`resume-1`)."""
    try:
        store.get_resume(DEMO_USER, DEMO_RESUME_ID)
        return
    except ResumeNotFoundError:
        pass
    now = utc_now()
    store.create_resume(
        user_id=DEMO_USER,
        original_filename="jane-doe.pdf",
        mime_type="application/pdf",
        file_size=12_000,
        blob_uri=f"{DEMO_USER}/{DEMO_RESUME_ID}/jane-doe.pdf",
        checksum_sha256="a" * 64,
        text_preview="Jane Doe — Python Azure Kubernetes APIs platform engineer",
        resume_id=DEMO_RESUME_ID,
    )
    snapshot = StructuredResume(
        contact=ResumeContact(
            resume_id=DEMO_RESUME_ID,
            full_name="Jane Doe",
            email="jane@example.com",
            phone="+15555550100",
            location="Remote",
            updated_at=now,
        ),
        skills=[
            ResumeSkill(resume_id=DEMO_RESUME_ID, name="Python", updated_at=now),
            ResumeSkill(resume_id=DEMO_RESUME_ID, name="Azure", updated_at=now),
            ResumeSkill(resume_id=DEMO_RESUME_ID, name="Kubernetes", updated_at=now),
            ResumeSkill(resume_id=DEMO_RESUME_ID, name="APIs", updated_at=now),
        ],
        experiences=[
            ResumeExperience(
                resume_id=DEMO_RESUME_ID,
                title="Staff Platform Engineer",
                company="Acme",
                start_date="2020-01",
                end_date="2024-06",
                description="Built Python services, Azure pipelines, and Kubernetes platforms.",
                updated_at=now,
            )
        ],
        educations=[
            ResumeEducation(
                resume_id=DEMO_RESUME_ID,
                institution="MIT",
                degree="BS",
                field="Computer Science",
                start_date="2015-09",
                end_date="2019-06",
                updated_at=now,
            )
        ],
    )
    store.record_parse_success(DEMO_USER, DEMO_RESUME_ID, snapshot, parsing_confidence=88)

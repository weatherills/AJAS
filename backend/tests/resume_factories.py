"""Factories and sample files for Resume Management tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter

from app.resumes.models import (
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
    ResumeSkill,
    StructuredResume,
)
from app.resumes.validation import utc_now

ASSETS = Path(__file__).resolve().parent / "assets" / "resumes"
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def sample_pdf_bytes(text: str = "Skills: Python, Azure") -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = BytesIO()
    writer.write(buf)
    # pypdf blank pages have no text; tests that need text use DOCX.
    _ = text
    return buf.getvalue()


def sample_docx_bytes(text: str = "Skills: Python, Azure") -> bytes:
    from docx import Document

    document = Document()
    document.add_paragraph(text)
    buf = BytesIO()
    document.save(buf)
    return buf.getvalue()


def write_sample_assets() -> tuple[Path, Path]:
    ASSETS.mkdir(parents=True, exist_ok=True)
    pdf_path = ASSETS / "sample.pdf"
    docx_path = ASSETS / "sample.docx"
    pdf_path.write_bytes(sample_pdf_bytes())
    docx_path.write_bytes(sample_docx_bytes("Skills: Python, Azure\nExperience: Engineer at Acme"))
    return pdf_path, docx_path


def make_contact(resume_id: str, *, full_name: str = "Jane Doe", email: str = "jane@example.com") -> ResumeContact:
    return ResumeContact(
        resume_id=resume_id,
        full_name=full_name,
        email=email,
        updated_at=utc_now(),
    )


def make_skill(resume_id: str, name: str, *, order_index: int = 0) -> ResumeSkill:
    return ResumeSkill(resume_id=resume_id, name=name, order_index=order_index, updated_at=utc_now())


def make_experience(resume_id: str, **kwargs) -> ResumeExperience:
    payload = dict(
        resume_id=resume_id,
        title="Engineer",
        company="Acme",
        start_date="2020-01",
        end_date="2021-06",
        updated_at=utc_now(),
    )
    payload.update(kwargs)
    return ResumeExperience(**payload)


def make_education(resume_id: str, **kwargs) -> ResumeEducation:
    payload = dict(
        resume_id=resume_id,
        institution="MIT",
        degree="BS",
        start_date="2015-09",
        end_date="2019-06",
        updated_at=utc_now(),
    )
    payload.update(kwargs)
    return ResumeEducation(**payload)


def make_snapshot(*, resume_id: str = "pending", skills=None, experiences=None, educations=None, contact=None) -> StructuredResume:
    return StructuredResume(
        contact=contact,
        skills=skills or [make_skill(resume_id, "Python")],
        experiences=experiences or [make_experience(resume_id)],
        educations=educations or [],
    )

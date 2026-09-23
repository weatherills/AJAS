"""Auto-Apply Backend PRD leftovers: AV scan, extractable text, E.164, dates."""

from __future__ import annotations

import pytest

from app.auto_apply.attachments import POLICY, inspect_attachment_bytes, validate_attachment
from app.auto_apply.blobs import InMemoryBlobStore
from app.auto_apply.cover import COVER_MAX_TOKENS, extract_cover_upload
from app.auto_apply.errors import AutoApplyValidationError
from app.auto_apply.memory import InMemoryAutoApplyStore
from app.auto_apply.queues import InMemoryJobQueue
from app.auto_apply.runtime import set_service
from app.auto_apply.service import AutoApplyService
from app.auto_apply.validation import normalize_e164, validate_apply_fields, validate_work_history
from app.config import get_settings
from app.mail.scan import EICAR_SIGNATURE

USER = "user-1"


@pytest.fixture
def svc(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = AutoApplyService(store=InMemoryAutoApplyStore(), queue=InMemoryJobQueue(), blobs=InMemoryBlobStore())
    set_service(service)
    yield service
    set_service(None)
    get_settings.cache_clear()


def test_attachment_policy_requires_virus_scan_and_extractable_text():
    assert POLICY["resume"]["virusScan"] is True
    assert POLICY["coverLetter"]["virusScan"] is True
    assert POLICY["resume"]["textExtractable"] is True
    validate_attachment(kind="resume", content_type="application/pdf", size=1000)
    with pytest.raises(AutoApplyValidationError, match="antivirus"):
        validate_attachment(
            kind="resume",
            content_type="application/pdf",
            size=len(EICAR_SIGNATURE),
            data=EICAR_SIGNATURE,
            filename="resume.pdf",
        )
    with pytest.raises(AutoApplyValidationError, match="antivirus"):
        inspect_attachment_bytes(
            kind="coverLetter",
            content_type="text/plain",
            data=EICAR_SIGNATURE,
            filename="cover.txt",
        )


def test_cover_extract_rejects_eicar():
    with pytest.raises(AutoApplyValidationError, match="antivirus"):
        extract_cover_upload(filename="letter.txt", content_type="text/plain", data=EICAR_SIGNATURE)


def test_create_request_rejects_eicar_inline_resume(svc):
    with pytest.raises(AutoApplyValidationError, match="antivirus"):
        svc.create_request(
            USER,
            {
                "job_source": "greenhouse",
                "job_posting_id": "job-av",
                "posting_url": "https://boards.greenhouse.io/acme/jobs/av",
                "resume_id": "resume-active",
                "cover_letter_mode": "none",
                "consent_approved": True,
                "resume_bytes": EICAR_SIGNATURE,
                "resume_content_type": "application/pdf",
                "resume_filename": "cv.pdf",
            },
        )


def test_cover_generation_budget_is_1000_tokens():
    assert COVER_MAX_TOKENS == 1000


def test_phone_normalizes_to_e164_and_rejects_short_numbers():
    assert normalize_e164("555-555-0100") == "+15555550100"
    assert normalize_e164("+15555550100") == "+15555550100"
    validate_apply_fields(
        {"answers": {"full_name": "Alex Jobseeker", "email": "alex@example.com", "phone": "555-555-0100"}},
        {},
    )
    with pytest.raises(AutoApplyValidationError, match="E.164"):
        validate_apply_fields(
            {"answers": {"full_name": "Alex Jobseeker", "email": "alex@example.com", "phone": "12"}},
            {},
        )


def test_inspect_rejects_empty_text_when_extractable_required():
    with pytest.raises(AutoApplyValidationError, match="extractable"):
        inspect_attachment_bytes(
            kind="coverLetter",
            content_type="text/plain",
            data=b"   ",
            filename="empty.txt",
            require_text=True,
        )
    text = inspect_attachment_bytes(
        kind="coverLetter",
        content_type="text/plain",
        data=b"Dear hiring team",
        filename="cover.txt",
        require_text=True,
    )
    assert text == "Dear hiring team"


def test_location_and_work_history_rules():
    validate_apply_fields(
        {
            "answers": {
                "full_name": "Alex Jobseeker",
                "email": "alex@example.com",
                "location": "US-TX",
                "experience": [{"start": "2020-01", "end": "present"}],
            }
        },
        {},
    )
    validate_apply_fields(
        {
            "answers": {
                "full_name": "Alex Jobseeker",
                "email": "alex@example.com",
                "location": "Austin, TX",
                "experience": [{"start": "2020-01", "end": "2022-06"}],
            }
        },
        {},
    )
    with pytest.raises(AutoApplyValidationError, match="Location"):
        validate_apply_fields(
            {"answers": {"full_name": "Alex Jobseeker", "email": "alex@example.com", "location": "###"}},
            {},
        )
    with pytest.raises(AutoApplyValidationError, match="coherent"):
        validate_work_history({"experience": [{"start": "2024-01", "end": "2020-01"}]})

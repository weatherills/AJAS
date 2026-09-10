"""Sprint 8 polish: resume contact overlay for Auto-Apply, PROFILE fallback."""

from __future__ import annotations

import json

from app.auto_apply.blobs import InMemoryBlobStore
from app.auto_apply.memory import InMemoryAutoApplyStore
from app.auto_apply.queues import InMemoryJobQueue
from app.auto_apply.runtime import set_service as set_auto_apply
from app.auto_apply.service import AutoApplyService, PROFILE
from app.resumes.blobs import InMemoryBlobStore as ResumeBlobStore
from app.resumes.demo import DEMO_RESUME_ID, DEMO_USER, seed_demo_resume
from app.resumes.memory import InMemoryResumeStore
from app.resumes.parser import HeuristicResumeParser
from app.resumes.queueing import InMemoryParseQueue
from app.resumes.runtime import set_service as set_resume
from app.resumes.service import ResumeService


def _create_body(**overrides):
    payload = {
        "job_source": "greenhouse",
        "job_posting_id": "job-staff",
        "posting_url": "https://boards.greenhouse.io/acme/jobs/staff",
        "resume_id": "resume-active",
        "cover_letter_mode": "generate",
        "consent_approved": True,
    }
    payload.update(overrides)
    return payload


def _autofill_map(detail: dict) -> dict[str, str]:
    return {row["field_key"]: row["value"] for row in detail["autofill"]}


def test_create_uses_resume_contact_when_resume_service_set():
    resume_svc = ResumeService(
        store=InMemoryResumeStore(),
        blobs=ResumeBlobStore(),
        queue=InMemoryParseQueue(),
        parser=HeuristicResumeParser(),
    )
    seed_demo_resume(resume_svc.store)
    set_resume(resume_svc)
    blobs = InMemoryBlobStore()
    service = AutoApplyService(store=InMemoryAutoApplyStore(), queue=InMemoryJobQueue(), blobs=blobs)
    set_auto_apply(service)
    try:
        _status, created = service.create_request(
            DEMO_USER,
            _create_body(resume_id=DEMO_RESUME_ID),
        )
        detail = service.get_request(DEMO_USER, created["request_id"])
        fields = _autofill_map(detail)
        assert fields["full_name"] == "Jane Doe"
        assert fields["email"] == "jane@example.com"
        assert "Jane Doe" in (detail["cover_letter_text"] or "")
        payload = blobs.get(f"provider_payloads/{DEMO_USER}/{created['request_id']}.json")
        assert payload is not None
        body = json.loads(payload.decode("utf-8"))
        assert body["fields"]["first_name"] == "Jane"
        assert body["fields"]["last_name"] == "Doe"
        assert body["fields"]["email"] == "jane@example.com"
    finally:
        set_resume(None)
        set_auto_apply(None)


def test_create_falls_back_to_profile_without_resume_service():
    blobs = InMemoryBlobStore()
    service = AutoApplyService(store=InMemoryAutoApplyStore(), queue=InMemoryJobQueue(), blobs=blobs)
    set_auto_apply(service)
    try:
        _status, created = service.create_request("user-1", _create_body())
        detail = service.get_request("user-1", created["request_id"])
        fields = _autofill_map(detail)
        assert fields["full_name"] == PROFILE["full_name"]
        assert fields["email"] == PROFILE["email"]
        assert PROFILE["full_name"] in (detail["cover_letter_text"] or "")
    finally:
        set_auto_apply(None)


def test_apply_form_answers_override_resume_contact():
    resume_svc = ResumeService(
        store=InMemoryResumeStore(),
        blobs=ResumeBlobStore(),
        queue=InMemoryParseQueue(),
        parser=HeuristicResumeParser(),
    )
    seed_demo_resume(resume_svc.store)
    set_resume(resume_svc)
    service = AutoApplyService(store=InMemoryAutoApplyStore(), queue=InMemoryJobQueue(), blobs=InMemoryBlobStore())
    set_auto_apply(service)
    try:
        _status, created = service.create_request(
            DEMO_USER,
            _create_body(
                resume_id=DEMO_RESUME_ID,
                answers={"full_name": "Pat Override", "email": "pat@example.com"},
            ),
        )
        detail = service.get_request(DEMO_USER, created["request_id"])
        fields = _autofill_map(detail)
        assert fields["full_name"] == "Pat Override"
        assert fields["email"] == "pat@example.com"
        assert "Pat Override" in (detail["cover_letter_text"] or "")
    finally:
        set_resume(None)
        set_auto_apply(None)

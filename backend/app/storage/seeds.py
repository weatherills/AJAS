"""Deterministic seed documents for local dev and e2e tests."""

from __future__ import annotations

from typing import Any

from app.storage.dal import CosmosDAL
from app.storage.entities import Application, EventLog, JobPosting, MailThread, StoredResume, User

SEED_USER_ID = "seed-user-001"
SEED_RESUME_ID = "seed-resume-001"
SEED_JOB_ID = "seed-job-001"
SEED_APPLICATION_ID = "seed-application-001"
SEED_THREAD_ID = "seed-thread-001"
SEED_ACCOUNT_ID = "seed-account-001"
SEED_MATCH_ID = "seed-match-001"
STAMP = "2026-01-15T12:00:00+00:00"


def _user() -> dict[str, Any]:
    return User(
        id=SEED_USER_ID,
        email="ada@ajas.dev",
        display_name="Ada Lovelace",
        status="active",
        created_at=STAMP,
        updated_at=STAMP,
    ).model_dump()


def _job() -> dict[str, Any]:
    return JobPosting(
        id=SEED_JOB_ID,
        canonical_key="staff-platform-engineer|seattle-wa|acme",
        dedupe_hash="a" * 64,
        title="Staff Platform Engineer",
        company="Acme",
        location="Seattle, WA",
        employment_type="full-time",
        apply_url="https://boards.greenhouse.io/acme/jobs/1",
        is_active=True,
        source="greenhouse",
        created_at=STAMP,
        updated_at=STAMP,
    ).model_dump()


def _resume() -> dict[str, Any]:
    return StoredResume(
        id=SEED_RESUME_ID,
        user_id=SEED_USER_ID,
        original_filename="ada-lovelace.pdf",
        mime_type="application/pdf",
        file_size=2048,
        blob_uri=f"{SEED_USER_ID}/{SEED_RESUME_ID}/ada-lovelace.pdf",
        checksum_sha256="b" * 64,
        processing_status="parsed",
        is_deleted=False,
        created_at=STAMP,
        updated_at=STAMP,
    ).model_dump()


def _application() -> dict[str, Any]:
    return Application(
        id=SEED_APPLICATION_ID,
        user_id=SEED_USER_ID,
        job_id=SEED_JOB_ID,
        resume_id=SEED_RESUME_ID,
        vendor="greenhouse",
        status="draft",
        approved=False,
        created_at=STAMP,
        updated_at=STAMP,
    ).model_dump()


def _thread() -> dict[str, Any]:
    return MailThread(
        id=SEED_THREAD_ID,
        email_account_id=SEED_ACCOUNT_ID,
        user_id=SEED_USER_ID,
        graph_conversation_id="conv-seed-001",
        subject="Staff Platform Engineer at Acme",
        job_posting_id=SEED_JOB_ID,
        application_id=SEED_APPLICATION_ID,
        last_message_at=STAMP,
        created_at=STAMP,
        updated_at=STAMP,
    ).model_dump()


def _match() -> dict[str, Any]:
    return {
        "id": SEED_MATCH_ID,
        "user_id": SEED_USER_ID,
        "job_id": SEED_JOB_ID,
        "resume_id": SEED_RESUME_ID,
        "status": "PENDING",
        "source": "ai",
        "job_title": "Staff Platform Engineer",
        "company": "Acme",
        "location": "Seattle, WA",
        "ai_score": 0.91,
        "suggestion": "approve",
        "queued_at": STAMP,
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def _event() -> dict[str, Any]:
    return EventLog(
        id="seed-event-001",
        user_id=SEED_USER_ID,
        event_type="SEED",
        entity_type="user",
        entity_id=SEED_USER_ID,
        payload={"source": "seed"},
        occurred_at=STAMP,
    ).model_dump()


def seed_documents() -> dict[str, list[dict[str, Any]]]:
    """Map of container id → documents. Safe to upsert repeatedly."""
    return {
        "users": [_user()],
        "job_postings_canonical": [_job()],
        "resumes": [_resume()],
        "auto_apply_attempts": [_application()],
        "email_threads": [_thread()],
        "matches": [_match()],
        "event_log": [_event()],
    }


def apply_seed(dal: CosmosDAL) -> dict[str, int]:
    counts: dict[str, int] = {}
    for container, rows in seed_documents().items():
        for row in rows:
            dal.upsert(container, row)
        counts[container] = len(rows)
    return counts


SAMPLE_RESUME_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
SAMPLE_JOB_RAW = b'{"id":"seed-job-001","title":"Staff Platform Engineer"}\n'


def seed_blobs(put) -> dict[str, str]:
    """Upload sample resume + job-raw artifacts. ``put(container, key, data)``."""
    from app.storage.blob_layout import checksum_blob_name, job_raw_key, resume_key

    resume_name = checksum_blob_name("ada-lovelace.pdf", "b" * 64)
    resume_path = resume_key(SEED_USER_ID, SEED_RESUME_ID, resume_name)
    raw_path = job_raw_key("seed-tenant-001", "post-seed-001", STAMP)
    put("resumes", resume_path, SAMPLE_RESUME_BYTES)
    put("job-raw", raw_path, SAMPLE_JOB_RAW)
    return {"resumes": resume_path, "job-raw": raw_path}

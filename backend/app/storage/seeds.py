"""Deterministic seed documents for local dev and e2e tests."""

from __future__ import annotations

from typing import Any

from app.mail.keys import body_hash
from app.storage.dal import CosmosDAL
from app.storage.entities import Application, EventLog, JobPosting, MailThread, StoredResume, User
from app.storage.epic import persist_saved, settings_document
from app.storage.versions import version_document

SEED_USER_ID = "seed-user-001"
SEED_RESUME_ID = "seed-resume-001"
SEED_JOB_ID = "seed-job-001"
SEED_APPLICATION_ID = "seed-application-001"
SEED_THREAD_ID = "seed-thread-001"
SEED_ACCOUNT_ID = "seed-account-001"
SEED_MATCH_ID = "seed-match-001"
SEED_MATCH_LOW_ID = "seed-match-low"
SEED_DECISION_ID = "seed-decision-001"
SEED_VERSION_ID = "seed-resume-v1"
SEED_VERSION_OLD_ID = "seed-resume-v0"
SEED_MESSAGE_ID = "seed-message-001"
SEED_LEARNING_EVENT_ID = "seed-learning-001"
SEED_METRICS_ID = "seed-metrics-001"
SEED_JOB_LEVER_ID = "seed-job-lever-001"
SEED_CRAWL_ID = "seed-crawl-001"
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
    row = JobPosting(
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
    row["posted_at"] = STAMP
    return row


def _job_lever() -> dict[str, Any]:
    return {
        "id": SEED_JOB_LEVER_ID,
        "canonical_key": "intern|remote|beta",
        "dedupe_hash": "c" * 64,
        "title": "Intern",
        "company": "Beta",
        "location": "Remote",
        "employment_type": "internship",
        "apply_url": "https://jobs.lever.co/beta/intern",
        "is_active": True,
        "source": "lever",
        "posted_at": STAMP,
        "created_at": STAMP,
        "updated_at": STAMP,
    }


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
    score = 0.91
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
        "ai_score": score,
        "saved": persist_saved(score=score, threshold=70),
        "suggestion": "approve",
        "queued_at": STAMP,
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def _match_below_threshold() -> dict[str, Any]:
    score = 0.41
    return {
        "id": SEED_MATCH_LOW_ID,
        "user_id": SEED_USER_ID,
        "job_id": SEED_JOB_LEVER_ID,
        "resume_id": SEED_RESUME_ID,
        "status": "PENDING",
        "source": "ai",
        "job_title": "Intern",
        "company": "Beta",
        "location": "Remote",
        "ai_score": score,
        "saved": persist_saved(score=score, threshold=70),
        "suggestion": "reject",
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


def _settings() -> dict[str, Any]:
    return settings_document(
        SEED_USER_ID,
        created_at=STAMP,
        updated_at=STAMP,
        match_threshold=70,
        greenhouse_enabled=True,
        lever_enabled=True,
        auto_apply_enabled=False,
    )


def _settings_strict() -> dict[str, Any]:
    return settings_document(
        "seed-user-strict",
        created_at=STAMP,
        updated_at=STAMP,
        match_threshold=90,
        greenhouse_enabled=True,
        lever_enabled=False,
        auto_apply_enabled=False,
        theme="dark",
    )


def _job_source() -> dict[str, Any]:
    return {
        "id": "greenhouse",
        "name": "Greenhouse",
        "kind": "board",
        "is_enabled": True,
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def _job_source_lever() -> dict[str, Any]:
    return {
        "id": "lever",
        "name": "Lever",
        "kind": "board",
        "is_enabled": True,
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def _crawl() -> dict[str, Any]:
    return {
        "id": SEED_CRAWL_ID,
        "source_tenant_id": "seed-tenant-001",
        "source_id": "greenhouse",
        "status": "succeeded",
        "started_at": STAMP,
        "finished_at": STAMP,
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def _decision() -> dict[str, Any]:
    return {
        "id": SEED_DECISION_ID,
        "user_id": SEED_USER_ID,
        "job_id": SEED_JOB_ID,
        "match_id": SEED_MATCH_ID,
        "decision": "approve",
        "source": "manual",
        "comment": "Strong platform fit",
        "decided_at": STAMP,
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def _review_history() -> dict[str, Any]:
    return {
        "id": "seed-audit-001",
        "user_id": SEED_USER_ID,
        "match_id": SEED_MATCH_ID,
        "job_id": SEED_JOB_ID,
        "event_type": "DECISION_RECORDED",
        "occurred_at": STAMP,
        "created_at": STAMP,
        "payload": {"decision": "approve"},
    }


def _application_event(status: str, suffix: str) -> dict[str, Any]:
    return {
        "id": f"seed-app-event-{suffix}",
        "auto_apply_id": SEED_APPLICATION_ID,
        "user_id": SEED_USER_ID,
        "event_type": status,
        "created_ts": STAMP,
        "created_at": STAMP,
    }


def _resume_versions() -> list[dict[str, Any]]:
    current = version_document(
        version_id=SEED_VERSION_ID,
        resume_id=SEED_RESUME_ID,
        user_id=SEED_USER_ID,
        version=2,
        blob_uri=f"{SEED_USER_ID}/{SEED_RESUME_ID}/ada-lovelace.pdf",
        original_filename="ada-lovelace.pdf",
        mime_type="application/pdf",
        file_size=2048,
        checksum_sha256="b" * 64,
        created_at=STAMP,
    )
    previous = version_document(
        version_id=SEED_VERSION_OLD_ID,
        resume_id=SEED_RESUME_ID,
        user_id=SEED_USER_ID,
        version=1,
        blob_uri=f"{SEED_USER_ID}/{SEED_RESUME_ID}/ada-lovelace.v1.pdf",
        original_filename="ada-draft.pdf",
        mime_type="application/pdf",
        file_size=1024,
        checksum_sha256="d" * 64,
        is_deleted=True,
        created_at=STAMP,
    )
    return [current, previous]


def _message() -> dict[str, Any]:
    body = "Hi Ada, thanks for applying to Staff Platform Engineer."
    return {
        "id": SEED_MESSAGE_ID,
        "email_account_id": SEED_ACCOUNT_ID,
        "email_thread_id": SEED_THREAD_ID,
        "graph_message_id": "graph-msg-seed-001",
        "from_address": "recruiter@acme.test",
        "to_addresses": ["ada@ajas.dev"],
        "subject": "Staff Platform Engineer at Acme",
        "body_text": body,
        "body_html": None,
        "body_hash": body_hash(body, None),
        "received_at": STAMP,
        "created_at": STAMP,
        "updated_at": STAMP,
        "has_attachments": True,
    }


def _attachment() -> dict[str, Any]:
    return {
        "id": "seed-att-001",
        "email_account_id": SEED_ACCOUNT_ID,
        "message_id": SEED_MESSAGE_ID,
        "filename": "jd.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 4096,
        "blob_uri": f"{SEED_ACCOUNT_ID}/{SEED_MESSAGE_ID}/jd.pdf",
        "is_inline": False,
        "created_at": STAMP,
    }


def _learning_event() -> dict[str, Any]:
    return {
        "id": SEED_LEARNING_EVENT_ID,
        "user_id": SEED_USER_ID,
        "recommendation_id": "seed-rec-001",
        "match_id": SEED_MATCH_ID,
        "decision": "approve",
        "score": 0.91,
        "decided_at": STAMP,
        "created_at": STAMP,
    }


def _metrics_snapshot() -> dict[str, Any]:
    return {
        "id": SEED_METRICS_ID,
        "scope_ref": f"user:{SEED_USER_ID}",
        "scope_type": "user",
        "user_id": SEED_USER_ID,
        "precision": 0.82,
        "recall": 0.61,
        "sample_count": 24,
        "window_end": STAMP,
        "weight_config_id": "weight-global-v1",
        "created_at": STAMP,
    }


def seed_documents() -> dict[str, list[dict[str, Any]]]:
    """Map of container id → documents. Safe to upsert repeatedly."""
    application = _application()
    application["status"] = "submitted"
    return {
        "users": [_user()],
        "job_postings_canonical": [_job(), _job_lever()],
        "resumes": [_resume()],
        "resume_versions": _resume_versions(),
        "auto_apply_attempts": [application],
        "status_events": [
            _application_event("created", "created"),
            _application_event("queued", "pending"),
            _application_event("submission_succeeded", "completed"),
        ],
        "email_threads": [_thread()],
        "email_messages": [_message()],
        "email_attachments": [_attachment()],
        "matches": [_match(), _match_below_threshold()],
        "decision_events": [_decision()],
        "audit_events": [_review_history()],
        "event_log": [_event()],
        "user_settings": [_settings(), _settings_strict()],
        "job_sources": [_job_source(), _job_source_lever()],
        "source_fetch_runs": [_crawl()],
        "decision_log": [_learning_event()],
        "metrics_snapshot": [_metrics_snapshot()],
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

"""PRD container/DAO Kanban: resumes, review, auto-apply, matching, email, settings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.auto_apply.constants import APPLY_RUNS_TTL_SECONDS, ATTEMPTS_INDEXING
from app.mail.constants import MESSAGES_INDEXING, THREADS_INDEXING
from app.resumes.constants import PARSED_TTL_SECONDS, RESUMES_INDEXING_POLICY
from app.review.constants import DECISIONS_INDEXING, MATCHES_INDEXING
from app.settings.constants import SETTINGS_INDEXING_POLICY, SOURCE_TOGGLES_INDEXING_POLICY
from app.storage.audit import events as audit_events
from app.storage.audit import reset as reset_audit
from app.storage.catalog import container_by_id
from app.storage.dao import (
    AutoApplyDAO,
    EmailDAO,
    MatchingDAO,
    ResumesDAO,
    ReviewDAO,
    SettingsDAO,
    domain_daos,
    ensure_mvp_containers,
)
from app.storage.dal import ConflictError, CosmosDAL
from app.storage.epic import resolve_container
from app.storage.pii import hash_text, redact
from app.storage.testing import FakeDatabase

REPO = Path(__file__).resolve().parents[2]
USER = "prd-user"


def _daos():
    db = FakeDatabase()
    ensure_mvp_containers(db)
    return domain_daos(CosmosDAL(db)), db


def _paths(policy: dict) -> list[list[str]]:
    return [[part["path"] for part in index] for index in policy.get("compositeIndexes") or []]


def test_resume_containers_indexes_ttl_and_dao_flow():
    daos, _ = _daos()
    dao: ResumesDAO = daos["resumes"]  # type: ignore[assignment]
    created_names = dao.ensure_resumes_containers(FakeDatabase())
    assert {"resumes", "resume_files", "resume_parsed"} <= set(created_names)
    assert resolve_container("resume_files") == "resume_versions"
    assert resolve_container("resume_parsed") == "resume_parse_events"
    assert container_by_id("resumes").partition_key == "/user_id"
    assert container_by_id("resume_files").id == "resume_versions"
    assert container_by_id("resume_parsed").default_ttl == PARSED_TTL_SECONDS == 90 * 86_400
    resume_paths = _paths(RESUMES_INDEXING_POLICY)
    assert ["/user_id", "/is_deleted", "/updated_at"] in resume_paths
    assert ["/userId", "/updatedAt"] in resume_paths
    assert ["/createdAt"] in resume_paths

    first = dao.create_resume(USER, id="resume-1", title="Staff CV")
    again = dao.create_resume(USER, id="resume-1", title="Staff CV")
    assert first["id"] == again["id"] == "resume-1"
    assert first["userId"] == USER
    assert first["title"] == "Staff CV"
    assert first["createdAt"]
    linked = dao.link_file(
        USER,
        first["id"],
        storagePath="blob://cv.pdf",
        mimeType="application/pdf",
        size=12,
        hash="abc",
    )
    assert linked["storagePath"] == "blob://cv.pdf"
    assert linked["mimeType"] == "application/pdf"
    assert linked["hash"] == "abc"
    parsed = dao.save_version(
        USER,
        first["id"],
        version=2,
        rawJson={"text": "raw resume should not persist"},
        skills=["python"],
        experience=[{"title": "Eng"}],
        education=[{"school": "U"}],
    )
    assert parsed["resume"]["primaryFileId"] == linked["id"]
    assert parsed["resume"]["parsedVersion"] == 2
    assert "raw resume should not persist" not in str(parsed["event"])
    assert parsed["event"]["rawJsonHash"] == hash_text(json.dumps({"text": "raw resume should not persist"}, sort_keys=True))
    second = dao.create_resume(USER, title="Older")
    dao.link_file(USER, second["id"], storagePath="blob://old.pdf")
    listed = dao.list_user_resumes(USER, limit=10)
    assert listed["items"][0]["id"] in {first["id"], second["id"]}
    assert "nextCursor" in listed
    with pytest.raises(ConflictError):
        dao.save_version(USER, first["id"], version=3, etag="stale")


def test_review_containers_queue_history_and_indexes():
    daos, _ = _daos()
    dao: ReviewDAO = daos["review"]  # type: ignore[assignment]
    created = dao.ensure_review_containers(FakeDatabase())
    assert "matches" in created
    assert "review_queue" in created
    assert "review_decisions" in created
    assert resolve_container("review_queue") == "matches"
    assert resolve_container("review_decisions") == "decision_events"
    match_paths = _paths(MATCHES_INDEXING)
    assert ["/user_id", "/status", "/queued_at"] in match_paths
    assert ["/userId", "/status"] in match_paths
    assert ["/queuedAt"] in match_paths
    assert ["/userId", "/jobId"] in match_paths
    decision_paths = _paths(DECISIONS_INDEXING)
    assert ["/userId", "/jobId", "/createdAt"] in decision_paths

    first = dao.enqueue_review_item(USER, jobId="job-1", resumeId="res-1", source="ai")
    second = dao.enqueue_review_item(USER, job_id="job-1", resume_id="res-other")
    assert first["status"] == "created"
    assert second["status"] == "existing"
    assert first["item"]["queueStatus"] == "queued"
    assert first["item"]["queuedAt"]
    decided = dao.save_decision(USER, first["item"]["id"], "reject", reason="not a fit", etag=first["item"]["_etag"])
    assert decided["decision"]["jobId"] == "job-1"
    history = dao.list_review_history(USER, job_id="job-1")
    assert history["items"][0]["decision"] == "reject"
    empty = dao.list_review_history(USER, job_id="missing")
    assert empty["items"] == []


def test_auto_apply_containers_indexes_ttl_state_machine_and_mappings():
    daos, _ = _daos()
    dao: AutoApplyDAO = daos["auto_apply"]  # type: ignore[assignment]
    created = dao.ensure_auto_apply_containers(FakeDatabase())
    assert {"apply_runs", "auto_apply_attempts", "cover_letters", "vendor_field_mappings", "form_field_mappings"} <= set(created)
    assert resolve_container("apply_attempts") == "auto_apply_attempts"
    assert resolve_container("form_field_mappings") == "vendor_field_mappings"
    assert container_by_id("apply_runs").partition_key == "/userId"
    assert container_by_id("apply_runs").default_ttl == APPLY_RUNS_TTL_SECONDS == 365 * 86_400
    assert container_by_id("auto_apply_attempts").default_ttl == 180 * 86_400
    apply_paths = _paths(container_by_id("apply_runs").indexing_policy)
    assert ["/userId", "/startedAt"] in apply_paths
    assert ["/userId", "/jobId"] in apply_paths
    attempt_paths = _paths(ATTEMPTS_INDEXING)
    assert ["/userId", "/jobId"] in attempt_paths
    assert ["/runId"] in attempt_paths

    run = dao.create_apply_run(USER, job_id="job-a", resume_id="res-a", method="api")
    assert run["item"]["status"] == "pending"
    running = dao.transition_run(USER, run["item"]["id"], "running", etag=run["item"]["_etag"])
    assert running["status"] == "running"
    with pytest.raises(ValueError):
        dao.transition_run(USER, run["item"]["id"], "pending", etag=running["_etag"])
    done = dao.transition_run(USER, run["item"]["id"], "needs_manual", etag=running["_etag"], error_code="CAPTCHA")
    assert done["status"] == "needs_manual"
    assert done["errorCode"] == "CAPTCHA"
    with pytest.raises(ConflictError):
        dao.transition_run(USER, run["item"]["id"], "failed", etag="stale")

    mapping = dao.upsert_form_field_mapping("greenhouse", "first_name", selector="#first", required=True, transform="trim")
    assert mapping["siteKey"] == "greenhouse"
    listed = dao.list_form_field_mappings("greenhouse")
    assert listed[0]["field"] == "first_name"
    letter = dao.save_cover_letter(USER, jobId="job-a", resumeId="res-a", body="Dear hiring", model="gpt")
    assert letter["userId"] == USER
    attempt = dao.append_attempt(USER, run["item"]["id"], job_id="job-a", resume_id="res-a", step="submit")
    assert attempt["runId"] == run["item"]["id"]


def test_matching_containers_deterministic_ids_and_evidence_ttl():
    daos, _ = _daos()
    dao: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    created = dao.ensure_matching_containers(FakeDatabase())
    assert {"match_records", "match_evidence"} <= set(created)
    assert container_by_id("match_records").partition_key == "/userId"
    assert container_by_id("match_evidence").default_ttl == 180 * 86_400
    evidence_paths = _paths(container_by_id("match_evidence").indexing_policy)
    assert ["/userId", "/matchId", "/createdAt"] in evidence_paths
    first = dao.create_match_record(USER, job_id="j1", resume_id="r1", score=70, model_version="v1")
    second = dao.create_match_record(USER, job_id="j1", resume_id="r1", score=71, model_version="v1")
    assert first["record"]["id"] == second["record"]["id"]
    batch = dao.upsert_evidence_batch(USER, first["record"]["id"], [{"type": "skill", "weight": 1, "orderIndex": 0, "snippet": "secret"}])
    assert "secret" not in str(batch)


def test_email_and_settings_containers_body_hash_and_indexes():
    daos, _ = _daos()
    email: EmailDAO = daos["email"]  # type: ignore[assignment]
    settings: SettingsDAO = daos["settings"]  # type: ignore[assignment]
    assert email.ensure_email_containers(FakeDatabase()) == ["email_threads", "email_messages", "email_attachments"]
    assert "user_settings" in settings.ensure_settings_containers(FakeDatabase())
    thread_paths = _paths(THREADS_INDEXING)
    assert ["/userId", "/externalThreadId"] in thread_paths
    message_paths = _paths(MESSAGES_INDEXING)
    assert ["/receivedAt"] in message_paths
    settings_paths = _paths(SETTINGS_INDEXING_POLICY)
    assert ["/userId", "/updatedAt"] in settings_paths
    toggle_paths = _paths(SOURCE_TOGGLES_INDEXING_POLICY)
    assert ["/userId", "/source"] in toggle_paths

    thread = email.upsert_thread("acct", USER, externalThreadId="ext-1", jobId="job-9")
    assert thread["externalThreadId"] == "ext-1"
    message = email.upsert_message(
        "acct",
        thread["id"],
        from_address="recruiter@acme.test",
        body_text="confidential offer",
        externalMessageId="msg-1",
    )
    assert message["bodyHash"] == hash_text("confidential offer")
    assert message["body_text"] == ""
    assert "confidential offer" not in str(message)
    attachment = email.add_attachment_meta("acct", message["id"], filename="jd.pdf", contentType="application/pdf", size=4, storagePath="blob://jd")
    assert attachment["storagePath"] == "blob://jd"
    listed = email.list_thread_messages("acct", thread["id"])
    assert listed["items"][0]["bodyHash"] == message["bodyHash"]

    prefs = settings.get_settings(USER)
    updated = settings.update_settings(
        USER,
        {"matchThreshold": 80, "timezone": "America/Los_Angeles", "quietHoursStart": "21:00", "quietHoursEnd": "07:00"},
        etag=prefs["_etag"],
    )
    assert updated["matchThreshold"] == 80
    assert updated["timezone"] == "America/Los_Angeles"
    toggles = settings.get_source_toggles(USER)
    flipped = settings.update_source_toggles(USER, {"source": "greenhouse", "isEnabled": False}, etag=toggles["_etag"])
    assert flipped["isEnabled"] is False
    assert any(row["source"] == "greenhouse" and row["isEnabled"] is False for row in flipped["sources"])


def test_db_ops_audit_events_and_pii_minimization():
    reset_audit()
    daos, _ = _daos()
    resumes: ResumesDAO = daos["resumes"]  # type: ignore[assignment]
    resumes.create_resume(USER, title="PII")
    ops = audit_events()
    assert any(row["op"] == "create" and row["container"] == "resumes" for row in ops)
    assert all("correlationId" in row and "latencyMs" in row for row in ops)
    masked = redact("email_messages", {"from_address": "ada@ajas.dev", "body_text": "secret", "body": "secret"})
    assert masked["from_address"].startswith("a***@")
    assert "***" in str(masked["body_text"])
    assert hash_text("x") != hash_text("y")
    prd = (REPO / ".codespring/PRDs/resume-management/database-prd-resume-management.md").read_text()
    assert "Child containers" in prd
    assert "child tables" not in prd.lower()

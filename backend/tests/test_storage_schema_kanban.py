"""Schema-plane Kanban: SQL tables mapped onto Cosmos containers + aliases."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.matching.constants import EVIDENCE_TTL_SECONDS, RECORDS_PK
from app.matching.records import match_record_id
from app.storage.catalog import container_by_id, container_catalog, render_cosmos_schema
from app.storage.dal import CosmosDAL
from app.storage.epic import catalog_covers_epic, resolve_container
from app.storage.housekeeping import PURGE_CONTAINERS
from app.storage.migrate import apply_migrations, migration_plan
from app.storage.pii import encrypt_fields, redact
from app.storage.schema_plane import (
    APPLICATION_STATUS,
    EMAIL_DIRECTION,
    EMAIL_PROVIDER,
    PARSE_QUEUE_STATES,
    PHYSICAL_CONTAINERS,
    TABLE_ALIASES,
    SchemaDAO,
    TenantIsolationError,
    UniqueConstraintError,
    assert_enum,
    contains_search,
    fts_query,
    stamp_computed,
)
from app.storage.seeds import apply_seed, seed_documents
from app.storage.sprocs import enqueue_hint_for, stored_logic_catalog
from app.storage.testing import FakeDatabase

REPO = Path(__file__).resolve().parents[2]
USER = "schema-user"
SECRET = "test-pii-secret"


def _dao():
    db = FakeDatabase()
    dal = CosmosDAL(db)
    dao = SchemaDAO(dal, secret=SECRET)
    dao.ensure_containers(db)
    return dao, dal, db


def test_matching_containers_alignment():
    records = container_by_id("match_records")
    evidence = container_by_id("match_evidence")
    assert records.id == "match_records"
    assert records.partition_key == RECORDS_PK == "/userId"
    assert "userId" in records.logical_unique
    assert evidence.default_ttl == EVIDENCE_TTL_SECONDS == 180 * 86_400
    composites = [[part["path"] for part in index] for index in records.indexing_policy["compositeIndexes"]]
    assert ["/userId", "/jobId"] in composites
    assert ["/userId", "/createdAt"] in composites
    mid = match_record_id(user_id="u", job_id="j", resume_id="r", model_version="matching-v1")
    again = match_record_id(user_id="u", job_id="j", resume_id="r", model_version="matching-v1")
    assert mid == again
    assert resolve_container("match_records") == "match_records"
    assert resolve_container("match_evidence") == "match_evidence"


def test_job_postings_schema_and_alias():
    assert resolve_container("job_postings") == "job_postings_canonical"
    spec = container_by_id("job_postings")
    assert spec.partition_key == "/id"
    assert "canonical_key" in spec.logical_unique
    assert "apply_url" in " ".join(spec.query_patterns)
    assert "scraped_at" in " ".join(spec.query_patterns)
    assert "status" in " ".join(spec.query_patterns)
    uniques = {tuple(paths) for paths in spec.unique_keys}
    assert ("/canonical_key",) in uniques
    assert ("/dedupe_hash",) in uniques


def test_resumes_schema_checksum_and_candidate():
    spec = container_by_id("resumes")
    assert spec.partition_key == "/user_id"
    assert "checksum_sha256" in spec.logical_unique
    assert "candidate_id" in " ".join(spec.query_patterns)
    dao, dal, _ = _dao()
    dal.create(
        "resumes",
        {
            "id": "resume-1",
            "user_id": USER,
            "candidate_id": "cand-1",
            "checksum_sha256": "aa" * 32,
            "original_filename": "cv.pdf",
            "blob_uri": "blob://cv.pdf",
        },
    )
    row = dao.read_tenant("resumes", "resume-1", user_id=USER, partition_key=USER)
    assert row["candidate_id"] == "cand-1"
    assert row["checksum_sha256"]


def test_candidates_unique_email_and_pii():
    dao, _, _ = _dao()
    first = dao.create_candidate(email="Ada@ajas.dev", name="Ada", phone="555-0100", candidate_id="cand-1")
    assert first["email"].startswith("enc.")
    assert first["phone"].startswith("enc.")
    with pytest.raises(UniqueConstraintError):
        dao.create_candidate(email="ada@ajas.dev", name="Other")
    masked = redact("candidates", first)
    assert masked["email"] == "[redacted]"


def test_applications_and_status_history_aliases():
    assert resolve_container("applications") == "auto_apply_attempts"
    assert resolve_container("application_status_history") == "status_events"
    assert resolve_container("application_events") == "status_events"
    attempts = container_by_id("applications")
    assert attempts.partition_key == "/user_id"
    assert attempts.default_ttl == 180 * 86_400
    history = container_by_id("application_status_history")
    assert history.id == "status_events"


def test_companies_and_recruiters():
    dao, _, _ = _dao()
    company = dao.create_company(name="Acme", domain="Acme.TEST", company_id="co-1")
    assert company["domain"] == "acme.test"
    with pytest.raises(UniqueConstraintError):
        dao.create_company(name="Acme Inc", domain="acme.test")
    rec = dao.create_recruiter(company_id="co-1", name="Riley", email="riley@acme.test", phone="555")
    assert rec["companyId"] == "co-1"
    assert rec["email"].startswith("enc.")
    spec = container_by_id("recruiters")
    assert spec.partition_key == "/companyId"
    assert container_by_id("companies").logical_unique == ("domain",)


def test_email_threads_and_messages():
    assert resolve_container("email_threads") == "email_threads"
    assert resolve_container("email_messages") == "email_messages"
    assert resolve_container("mail_threads") == "email_threads"
    assert resolve_container("mail_messages") == "email_messages"
    threads = container_by_id("email_threads")
    messages = container_by_id("email_messages")
    assert ("/graph_conversation_id",) in threads.unique_keys
    assert ("/graph_message_id",) in messages.unique_keys
    assert "bodyHash" in " ".join(messages.query_patterns)


def test_resume_parse_queue_states():
    dao, _, _ = _dao()
    item = dao.enqueue_parse(USER, "resume-1")
    assert item["status"] == "queued"
    running = dao.transition_parse(USER, item["id"], "processing")
    assert running["status"] == "processing"
    failed = dao.transition_parse(USER, item["id"], "failed", error="timeout")
    assert failed["retries"] == 1
    assert failed["error"] == "timeout"
    with pytest.raises(ValueError):
        dao.enqueue_parse(USER, "resume-1", status="bogus")
    assert container_by_id("resume_parse_queue").default_ttl == 7 * 86_400
    assert PARSE_QUEUE_STATES == {"queued", "processing", "done", "failed"}


def test_auto_apply_rules_and_outbox():
    dao, _, _ = _dao()
    rule = dao.upsert_rule(USER, conditions={"minScore": 80}, priority=1, enabled=True, rule_id="rule-1")
    assert rule["enabled"] is True
    first = dao.enqueue_outbox(event_type="application.submitted", payload={"id": "a1"}, dedupe_key="dedupe-1")
    again = dao.enqueue_outbox(event_type="application.submitted", payload={"id": "a1"}, dedupe_key="dedupe-1")
    assert first["id"] == again["id"] == "dedupe-1"
    assert container_by_id("integration_outbox").default_ttl == 14 * 86_400
    assert resolve_container("webhooks_outbox") == "integration_outbox"


def test_audit_logs_and_attachments():
    assert resolve_container("audit_logs") == "event_log"
    assert container_by_id("audit_logs").partition_key == "/user_id"
    dao, _, _ = _dao()
    att = dao.save_attachment(
        USER,
        kind="resume",
        filename="cv.pdf",
        mime_type="application/pdf",
        size=12,
        blob_uri="blob://cv.pdf",
        checksum="ff" * 32,
    )
    assert att["mimeType"] == "application/pdf"
    with pytest.raises(UniqueConstraintError):
        dao.save_attachment(
            USER,
            kind="resume",
            filename="cv2.pdf",
            mime_type="application/pdf",
            size=1,
            blob_uri="blob://cv2.pdf",
            checksum="ff" * 32,
        )


def test_dedup_constraints_indexes_and_fts():
    jobs = container_by_id("job_postings_canonical")
    resumes = container_by_id("resumes")
    companies = container_by_id("companies")
    assert "canonical_key" in jobs.logical_unique
    assert "checksum_sha256" in resumes.logical_unique
    assert companies.logical_unique == ("domain",)
    assert contains_search("Staff Platform Engineer", "platform")
    assert not contains_search("Staff Platform Engineer", " intern")
    assert "CONTAINS" in fts_query("title")
    dao, dal, _ = _dao()
    dal.create("job_postings_canonical", {"id": "job-1", "title": "Staff Platform Engineer", "description": "Python"})
    hits = dao.search_text("job_postings_canonical", "title", "platform", partition_key="job-1")
    assert hits and hits[0]["id"] == "job-1"
    scripts = {item["id"] for item in stored_logic_catalog()}
    assert "udf_contains" in scripts


def test_pii_encryption_retention_migrations_and_triggers():
    sealed = encrypt_fields("candidates", {"email": "ada@ajas.dev", "phone": "555"}, secret=SECRET)
    assert sealed["email"].startswith("enc.")
    assert "candidates" in PURGE_CONTAINERS
    assert "attachments" in PURGE_CONTAINERS
    plan = migration_plan()
    assert plan[2]["id"] == "ajas.cosmos.v3-schema-plane"
    db = FakeDatabase()
    applied = apply_migrations(db)
    assert applied["status"] == "applied"
    ids = {spec.id for spec in container_catalog()}
    assert set(PHYSICAL_CONTAINERS) <= ids
    rolled = stamp_computed({"id": "x", "status_history": [{"status": "submitted"}], "items": [1, 2]})
    assert rolled["status_rollup"] == "submitted"
    assert rolled["item_count"] == 2
    assert rolled["updated_at"]
    assert enqueue_hint_for("resume_parse_queue", {"id": "q1"})["queue"] == "resume-parse"
    scripts = db.get_container_client("candidates").scripts
    assert "trg_computedFields" in scripts.triggers
    assert "udf_contains" in scripts.udfs
    seeds = seed_documents()
    assert "candidates" in seeds
    counts = apply_seed(CosmosDAL(db))
    assert counts["companies"] == 1


def test_enums_inboxes_mail_aliases_and_auto_apply_runs():
    assert_enum("draft", APPLICATION_STATUS, field="status")
    assert_enum("inbound", EMAIL_DIRECTION, field="direction")
    assert_enum("microsoft_365", EMAIL_PROVIDER, field="provider")
    with pytest.raises(ValueError):
        assert_enum("sms", EMAIL_PROVIDER, field="provider")
    dao, _, _ = _dao()
    inbox = dao.create_inbox(recruiter_id="rec-1", provider="microsoft_365", address="r@acme.test")
    assert inbox["provider"] == "microsoft_365"
    assert resolve_container("recruiter_inboxes") == "recruiter_inboxes"
    assert resolve_container("thread_participants") == "email_recipients"
    assert "email_thread_id" in container_by_id("thread_participants").logical_unique
    assert resolve_container("email_attachments") == "email_attachments"
    assert resolve_container("auto_apply_runs") == "apply_runs"
    assert resolve_container("auto_apply_run_items") == "auto_apply_attempts"
    assert container_by_id("auto_apply_runs").partition_key == "/userId"


def test_matching_models_scrape_rate_limits_oauth_webhooks_rls_indexes():
    assert resolve_container("matching_models") == "model_registry"
    assert resolve_container("rate_limits") == "source_rate_limits"
    dao, dal, db = _dao()
    created = dao.ensure_containers(db)
    assert "scrape_jobs_queue" in created
    scrape = dao.enqueue_scrape(source="greenhouse", url="https://boards.greenhouse.io/x", fingerprint="abc123")
    assert scrape["id"] == "abc123"
    with pytest.raises(UniqueConstraintError):
        dao.enqueue_scrape(source="greenhouse", url="https://other", fingerprint="abc123")
    oauth = dao.save_oauth(USER, provider="microsoft_365", access_token="tok", refresh_token="ref")
    assert oauth["access_token"].startswith("enc.")
    opened = dao.read_oauth(USER, "microsoft_365")
    assert opened["access_token"] == "tok"
    hook = dao.register_webhook(event="application.submitted", target_url="https://hooks.test/a", secret="shh")
    assert hook["secret"].startswith("enc.")
    delivery = dao.record_delivery(hook["id"], payload_ref="out-1", status="pending")
    assert delivery["webhookId"] == hook["id"]
    assert container_by_id("webhook_deliveries").default_ttl == 90 * 86_400
    dal.create("resumes", {"id": "r-own", "user_id": USER})
    dal.create("resumes", {"id": "r-other", "user_id": "other"})
    dao.read_tenant("resumes", "r-own", user_id=USER, partition_key=USER)
    with pytest.raises(TenantIsolationError):
        dao.read_tenant("resumes", "r-other", user_id=USER, partition_key="other")
    assert catalog_covers_epic() == []
    for alias, physical in TABLE_ALIASES.items():
        assert resolve_container(alias) == physical
    scrape_spec = container_by_id("scrape_jobs_queue")
    assert scrape_spec.unique_keys == (("/fingerprint",),)


def test_schema_md_committed_includes_new_containers():
    rendered = render_cosmos_schema()
    committed = (REPO / "docs" / "cosmos.schema.md").read_text()
    assert rendered == committed
    for name in PHYSICAL_CONTAINERS:
        assert f"`{name}`" in committed

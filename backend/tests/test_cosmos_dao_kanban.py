"""Named Cosmos DAOs: CRUD, idempotency, indexes, housekeeping, ops contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.dlq import inspect as dlq_inspect
from app.dlq import reset as reset_dlq
from app.pagination import MAX_LIMIT, normalize_limit, request_limit_and_cursor
from app.storage.backup import CRITICAL_CONTAINERS, export_backup, import_backup
from app.storage.backfill import run_backfill
from app.storage.catalog import container_by_id, container_catalog, ttl_containers
from app.storage.dao import (
    MVP_CONTAINERS,
    AutoApplyDAO,
    EmailDAO,
    JobIngestDAO,
    LearningDAO,
    MatchingDAO,
    PrivacyDAO,
    ResumesDAO,
    ReviewDAO,
    SettingsDAO,
    apply_run_id,
    domain_daos,
    ensure_mvp_containers,
    seed_dao_defaults,
)
from app.storage.dal import ConflictError, CosmosDAL
from app.storage.housekeeping import run_housekeeping
from app.storage.jobs import run_housekeeping_job
from app.storage.loadtest import HOT_PATHS, run_load
from app.storage.migrate import apply_migrations, migration_plan
from app.storage.partitioning import SYNTHETIC_BUCKETS, partition_review, synthetic_partition
from app.storage.pii import redact
from app.storage.query_lint import CrossPartitionScanError, lint_query, reset_profiles, top_queries
from app.storage.schema_validate import SchemaValidationError, validate_item
from app.storage.seeds import SEED_USER_ID, apply_seed, seed_documents
from app.storage.testing import FakeDatabase

REPO = Path(__file__).resolve().parents[2]
USER = "dao-user-1"


@pytest.fixture
def dal():
    db = FakeDatabase()
    ensure_mvp_containers(db)
    return CosmosDAL(db)


@pytest.fixture
def daos(dal):
    return domain_daos(dal)


def test_mvp_containers_and_partition_keys(dal):
    ids = {spec.id for spec in container_catalog()}
    assert set(MVP_CONTAINERS) <= ids
    expected = {
        "apply_runs": "/userId",
        "auto_apply_attempts": "/user_id",
        "resumes": "/user_id",
        "resume_versions": "/resume_id",
        "job_postings_canonical": "/id",
        "job_postings_raw": "/source_tenant_id",
        "source_fetch_runs": "/source_tenant_id",
        "source_rate_limits": "/source_tenant_id",
        "email_threads": "/email_account_id",
        "email_messages": "/email_account_id",
        "email_attachments": "/email_account_id",
        "user_settings": "/user_id",
        "source_toggles": "/userId",
        "decision_log": "/user_id",
        "weight_config": "/weight_config_id",
        "privacy_requests": "/userId",
        "privacy_audit_log": "/userId",
        "match_records": "/userId",
        "match_evidence": "/userId",
        "scoring_runs": "/userId",
        "match_runs": "/user_id",
        "matches": "/user_id",
        "decision_events": "/user_id",
    }
    for name, pk in expected.items():
        assert container_by_id(name).partition_key == pk
    created = ensure_mvp_containers(FakeDatabase())
    assert set(MVP_CONTAINERS) <= set(created)


def test_ttl_retention_on_time_bound_containers():
    ttl = {spec.id: spec.default_ttl for spec in ttl_containers()}
    assert ttl["match_evidence"] == 180 * 86_400
    assert ttl["job_postings_raw"] == 90 * 86_400
    assert ttl["export_bundles"] == 7 * 86_400
    assert ttl["webhook_callbacks"] == 90 * 86_400
    assert ttl["event_log"] == 30 * 86_400
    assert container_by_id("matches").default_ttl is None
    assert container_by_id("apply_runs").default_ttl == 365 * 86_400
    assert container_by_id("user_settings").default_ttl is None


def test_composite_indexes_and_unique_keys():
    apply_runs = container_by_id("apply_runs")
    assert apply_runs.unique_keys == (("/idempotency_key",),)
    composites = [[part["path"] for part in index] for index in apply_runs.indexing_policy["compositeIndexes"]]
    assert ["/userId", "/startedAt"] in composites
    jobs = container_by_id("job_postings_canonical")
    assert jobs.unique_keys == (("/canonical_key",), ("/dedupe_hash",))
    matches = container_by_id("matches")
    paths = [[part["path"] for part in index] for index in matches.indexing_policy["compositeIndexes"]]
    assert ["/user_id", "/status", "/queued_at"] in paths
    for spec in container_catalog():
        pk = spec.partition_key
        for keys in spec.unique_keys:
            assert pk not in keys


def test_auto_apply_dao_ensure_run_attempt_status_list(dal, daos):
    dao: AutoApplyDAO = daos["auto_apply"]  # type: ignore[assignment]
    assert set(dao.ensure(FakeDatabase())) >= {"apply_runs", "auto_apply_attempts"}
    first = dao.create_apply_run(USER, job_id="job-1", resume_id="res-1", model_version="v1")
    second = dao.create_apply_run(USER, job_id="job-1", resume_id="res-1", model_version="v1")
    assert first["status"] == "created"
    assert second["status"] == "existing"
    assert first["item"]["id"] == second["item"]["id"] == apply_run_id(user_id=USER, job_id="job-1", resume_id="res-1", model_version="v1")
    attempt = dao.append_attempt(USER, first["item"]["id"], job_id="job-1", resume_id="res-1")
    assert attempt["run_id"] == first["item"]["id"]
    updated = dao.set_run_status(USER, first["item"]["id"], "submitted", etag=first["item"]["_etag"])
    assert updated["status"] == "submitted"
    with pytest.raises(ConflictError):
        dao.set_run_status(USER, first["item"]["id"], "failed", etag="stale")
    listed = dao.list_runs(USER, limit=10)
    assert listed["items"]
    assert "nextCursor" in listed
    assert listed["requestCharge"] >= 0


def test_resumes_dao_create_attach_parse_active_list(daos):
    dao: ResumesDAO = daos["resumes"]  # type: ignore[assignment]
    created = dao.create_resume(USER, original_filename="cv.pdf")
    version = dao.attach_file(USER, created["id"], original_filename="cv.pdf", blob_uri="blob://cv")
    assert version["resume_id"] == created["id"]
    parsed = dao.save_parsed_version(USER, created["id"], {"skills": ["python"]})
    assert parsed["resume"]["processing_status"] == "parsed"
    other = dao.create_resume(USER, original_filename="alt.pdf")
    active = dao.set_active(USER, created["id"])
    assert active["is_active"] is True
    listed = dao.list(USER)
    flags = {row["id"]: row.get("is_active") for row in listed["items"]}
    assert flags[created["id"]] is True
    assert flags[other["id"]] is False


def test_job_ingest_dao_upsert_dedupe_logs_rate_limit(daos):
    dao: JobIngestDAO = daos["job_ingest"]  # type: ignore[assignment]
    first = dao.upsert_posting(
        canonical_key="staff|seattle|acme",
        title="Staff Engineer",
        source="greenhouse",
        external_id="gh-1",
    )
    second = dao.upsert_posting(
        canonical_key="staff|seattle|acme",
        title="Staff Platform Engineer",
        source="greenhouse",
        external_id="gh-1",
    )
    assert first["status"] == "created"
    assert second["status"] == "updated"
    assert first["item"]["id"] == second["item"]["id"]
    details = dao.upsert_details("tenant-1", source_posting_id="gh-1", payload_ref="blob://raw")
    assert details["source_tenant_id"] == "tenant-1"
    run = dao.log_ingest_run("tenant-1", status="running")
    assert run["status"] == "running"
    limit = dao.set_rate_limit("tenant-1", tokens=12, backoff_until=None)
    assert dao.get_rate_limit("tenant-1")["tokens"] == 12
    assert limit["id"] == "tenant-1"
    found = dao.dedupe_by_external(canonical_key="staff|seattle|acme")
    assert found is not None
    with pytest.raises(SchemaValidationError):
        dao.upsert_posting(canonical_key="x", title="Nope", source="linkedin")


def test_email_dao_thread_message_attachments(daos):
    dao: EmailDAO = daos["email"]  # type: ignore[assignment]
    thread = dao.upsert_thread("acct-1", USER, subject="Offer")
    message = dao.upsert_message("acct-1", thread["id"], from_address="recruiter@acme.test", body_text="secret hello")
    meta = dao.add_attachment_meta("acct-1", message["id"], filename="jd.pdf", blob_uri="blob://jd")
    assert meta["filename"] == "jd.pdf"
    listed = dao.list_thread_messages("acct-1", thread["id"])
    assert listed["items"][0]["id"] == message["id"]
    assert listed["items"][0]["from_address"].endswith("acme.test")
    assert "***" in listed["items"][0]["from_address"]
    assert "secret hello" not in listed["items"][0]["body_text"]


def test_settings_dao_defaults_and_toggles(daos):
    dao: SettingsDAO = daos["settings"]  # type: ignore[assignment]
    settings = dao.get_settings(USER)
    assert settings["match_threshold"] == 70
    assert settings["greenhouse_enabled"] is True
    updated = dao.update_settings(USER, {"match_threshold": 85}, etag=settings["_etag"])
    assert updated["match_threshold"] == 85
    with pytest.raises(ConflictError):
        dao.update_settings(USER, {"match_threshold": 10}, etag="nope")
    toggles = dao.get_source_toggles(USER)
    assert toggles["greenhouse"] is True
    assert toggles["lever"] is True
    assert toggles["autoApply"] is False
    flipped = dao.update_source_toggles(USER, {"autoApply": True, "lever": False}, etag=toggles["_etag"])
    assert flipped["autoApply"] is True
    assert flipped["lever"] is False


def test_learning_dao_feedback_and_weights(daos):
    dao: LearningDAO = daos["learning"]  # type: ignore[assignment]
    first = dao.log_decision_feedback(USER, recommendation_id="rec-1", match_id="m1", decision="approve", score=0.9)
    second = dao.log_decision_feedback(USER, recommendation_id="rec-1", match_id="m1", decision="approve", score=0.9)
    assert first["id"] == second["id"]
    weights = dao.upsert_model_weight_overrides("weight-user-1", {"keyword": 0.3, "semantic": 0.7})
    assert weights["weight_config_id"] == "weight-user-1"
    assert weights["weights"]["semantic"] == 0.7


def test_privacy_dao_export_delete_audit_redaction(daos):
    dao: PrivacyDAO = daos["privacy"]  # type: ignore[assignment]
    export = dao.create_export_request(USER, note="pack")
    deletion = dao.create_deletion_request(USER, note="forget me")
    redaction = dao.log_redaction(USER, field="email", container="users")
    assert export["kind"] == "export"
    assert deletion["kind"] == "delete"
    assert redaction["action"] == "redact"
    listed = dao.list_requests(USER)
    kinds = {row["kind"] for row in listed["items"]}
    assert kinds == {"export", "delete"}


def test_matching_dao_records_evidence_scoring_runs(daos):
    dao: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    created = dao.create_match_record(
        USER, job_id="job-9", resume_id="res-9", score=88.5, evidence=["k8s"]
    )
    record_id = created["record"]["id"]
    fetched = dao.get(USER, record_id)
    assert fetched["score"] == 88.5
    listed = dao.list_records(USER, job_id="job-9")
    assert listed[0]["id"] == record_id
    evidence = dao.put_evidence_batch(USER, record_id, ["more proof"])
    assert evidence["ttl"] == 180 * 86_400
    run = dao.create_scoring_run(USER, resume_id="res-9", job_id="job-9")
    again = dao.create_scoring_run(USER, resume_id="res-9", job_id="job-9")
    assert run["status"] == "created"
    assert again["status"] == "existing"
    assert run["item"]["idempotency_key"] == again["item"]["idempotency_key"]


def test_review_dao_enqueue_list_decide_dedupe(daos):
    dao: ReviewDAO = daos["review"]  # type: ignore[assignment]
    first = dao.enqueue(USER, job_id="job-r", resume_id="res-r", job_title="Staff", ai_score=0.9)
    second = dao.enqueue(USER, job_id="job-r", resume_id="res-r", job_title="Staff", ai_score=0.9)
    assert first["status"] == "created"
    assert second["status"] == "existing"
    queue = dao.list_queue(USER)
    assert queue["items"][0]["id"] == first["item"]["id"]
    decided = dao.save_decision(USER, first["item"]["id"], "approve", etag=first["item"]["_etag"])
    assert decided["match"]["status"] == "APPROVED"
    assert decided["decision"]["decision"] == "approve"
    empty = dao.list_queue(USER)
    assert empty["items"] == []
    assert dao.dedupe(USER, job_id="job-r", resume_id="res-r")["id"] == first["item"]["id"]


def test_seed_defaults_and_minimal_seed_script(dal):
    docs = seed_documents()
    assert docs["user_settings"][0]["match_threshold"] == 70
    assert docs["source_toggles"][0]["greenhouse"] is True
    assert docs["apply_runs"][0]["userId"] == SEED_USER_ID
    assert docs["weight_config"][0]["is_active"] is True
    counts = apply_seed(dal)
    assert counts["users"] == 1
    defaults = seed_dao_defaults(dal, SEED_USER_ID)
    assert defaults["caps"]["matchThreshold"] == 70
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("seed_cosmos_dao", REPO / "scripts" / "seed_cosmos_dao.py")
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.seed(FakeDatabase())
    assert result["resumeId"]
    assert result["matchId"]
    assert result["jobId"]


def test_smoke_crud_and_idempotency_all_daos(daos):
    names = set(domain_daos(daos["auto_apply"]._dal))  # type: ignore[attr-defined]
    assert names == {
        "auto_apply",
        "resumes",
        "job_ingest",
        "email",
        "settings",
        "learning",
        "privacy",
        "matching",
        "review",
    }
    apply_dao: AutoApplyDAO = daos["auto_apply"]  # type: ignore[assignment]
    a = apply_dao.create_apply_run(USER, job_id="j", resume_id="r")
    b = apply_dao.create_apply_run(USER, job_id="j", resume_id="r")
    assert a["item"]["id"] == b["item"]["id"]
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    m1 = matching.create_match_record(USER, job_id="j", resume_id="r", score=70)
    m2 = matching.create_match_record(USER, job_id="j", resume_id="r", score=71)
    assert m1["record"]["id"] == m2["record"]["id"]


def test_housekeeping_prunes_match_versions_and_purges_soft_deleted(dal, daos):
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    resumes: ResumesDAO = daos["resumes"]  # type: ignore[assignment]
    for score in range(10):
        matching.create_match_record(USER, job_id="keep-job", resume_id="keep-res", score=float(score))
    resume = resumes.create_resume(USER, original_filename="old.pdf")
    dal.replace(
        "resumes",
        resume["id"],
        {
            **resume,
            "is_deleted": True,
            "deleted_at": (datetime.now(timezone.utc) - timedelta(days=800)).isoformat(),
        },
        etag=resume["_etag"],
    )
    result = run_housekeeping_job(dal, USER, keep=5, dry_run=False)
    assert result["prune"]["keep"] == 5
    assert result["prune"]["deleted"] >= 1
    remaining = matching.records.list_records(USER, job_id="keep-job", latest_only=False)
    versions = [row for row in remaining if not row.get("latest")]
    assert len(versions) <= 5
    assert result["purge"]["count"] >= 1
    assert "blobLifecycle" in result


def test_migrations_backfill_and_schema_version(dal):
    plan = migration_plan()
    assert plan[0]["version"] == 1
    assert plan[1]["id"] == "ajas.cosmos.v2-dao"
    assert plan[1]["backfill"] == "scripts/cosmos_backfill.py"
    db = FakeDatabase()
    applied = apply_migrations(db)
    assert applied["status"] == "applied"
    dal.upsert("matches", {"id": "m1", "user_id": USER, "status": "PENDING"})

    def mutate(row):
        row.setdefault("schemaVersion", 2)
        return row

    result = run_backfill(dal, "matches", mutate, partition_key=USER, ru_budget=400)
    assert result["updated"] >= 1
    assert result["schema"] == "ajas.cosmos.backfill.v2"


def test_ru_latency_top_queries_and_load_smoke(dal, daos):
    reset_profiles()
    review: ReviewDAO = daos["review"]  # type: ignore[assignment]
    review.enqueue(USER, job_id="j1", resume_id="r1", job_title="Eng", ai_score=0.8)
    review.list_queue(USER, limit=25)
    daos["resumes"].list(USER, limit=25)  # type: ignore[union-attr]
    top = top_queries(3)
    assert top
    assert all("ru" in row for row in top)
    load = run_load(iterations=5)
    assert set(HOT_PATHS) >= {"matches.list", "review.queue", "email.thread_messages"}
    assert load["ok"] is True
    assert load["ruPerOp"] <= 5.0


def test_hot_partition_protection_and_cross_partition_lint():
    review = partition_review()
    assert review["buckets"] == SYNTHETIC_BUCKETS
    assert "source_tenants" in review["skewWatch"]
    source = next(row for row in review["containers"] if row["id"] == "source_tenants")
    assert source["skewRisk"] is True
    assert synthetic_partition("greenhouse", "acme") != synthetic_partition("lever", "acme")
    blocked = lint_query("matches", "SELECT * FROM c")
    assert blocked.ok is False
    dal = CosmosDAL(FakeDatabase())
    dal.upsert("matches", {"id": "m1", "user_id": USER, "status": "PENDING"})
    with pytest.raises(CrossPartitionScanError):
        dal.query("matches", "SELECT * FROM c")
    page = dal.query("matches", "SELECT * FROM c", partition_key=USER)
    assert page.items[0]["id"] == "m1"


def test_pii_backup_dlq_pagination_etag_soft_delete_validation(dal, daos):
    reset_dlq()
    email: EmailDAO = daos["email"]  # type: ignore[assignment]
    thread = email.upsert_thread("acct-2", USER, subject="PII")
    email.upsert_message("acct-2", thread["id"], from_address="ada@ajas.dev", body_text="ssn-like")
    listed = email.list_thread_messages("acct-2", thread["id"], redact=True)
    assert listed["items"][0]["from_address"].startswith("a***@")
    masked = redact("users", {"id": USER, "email": "ada@ajas.dev"})
    assert masked["email"] == "a***@ajas.dev"

    apply_dao: AutoApplyDAO = daos["auto_apply"]  # type: ignore[assignment]
    run = apply_dao.create_apply_run(USER, job_id="backup", resume_id="r")
    dest = Path("/tmp/ajas-dao-backup")
    counts = export_backup(dal, dest, containers=CRITICAL_CONTAINERS)
    assert "apply_runs" in counts
    other = CosmosDAL(FakeDatabase())
    imported = import_backup(other, dest, containers=("apply_runs",))
    assert imported["apply_runs"] >= 1
    assert run["item"]["id"]

    dead = apply_dao.record_error(kind="apply", payload={"token": "secret", "runId": run["item"]["id"]}, replay_hint="retry")
    stored = dlq_inspect(dead["id"])
    assert stored is not None
    assert stored["payload"]["token"] == "[redacted]"
    assert stored["payload"]["replayHint"] == "retry"

    limit, cursor = request_limit_and_cursor({"limit": "10", "cursor": "abc"})
    assert limit == 10
    assert cursor == "abc"
    with pytest.raises(ValueError):
        normalize_limit(MAX_LIMIT + 1)
    with pytest.raises(ValueError):
        normalize_limit(0)

    resumes: ResumesDAO = daos["resumes"]  # type: ignore[assignment]
    resume = resumes.create_resume(USER, original_filename="gone.pdf")
    repo = resumes.repo("resumes")
    soft = repo.soft_delete(resume["id"], partition_key=USER)
    assert soft["is_deleted"] is True
    hidden = resumes.list(USER)
    assert resume["id"] not in {row["id"] for row in hidden["items"]}
    stale = datetime.now(timezone.utc) - timedelta(days=800)
    dal.replace(
        "resumes",
        resume["id"],
        {**soft, "deleted_at": stale.isoformat()},
        etag=soft["_etag"],
    )
    purged = run_housekeeping(dal, USER, dry_run=False)
    assert any(resume["id"] in ids for ids in purged["purge"]["deleted"].values())

    with pytest.raises(SchemaValidationError):
        validate_item("resumes", {"id": "x"})
    with pytest.raises(SchemaValidationError):
        validate_item("matches", {"id": "m", "user_id": USER, "job_id": "j", "resume_id": "r", "status": "NOPE"})
    ok = validate_item(
        "matches",
        {"id": "m", "user_id": USER, "job_id": "j", "resume_id": "r", "status": "PENDING"},
    )
    assert ok["status"] == "PENDING"


def test_schema_doc_regenerates_unique_keys():
    from app.storage.catalog import render_cosmos_schema

    rendered = render_cosmos_schema()
    committed = (REPO / "docs" / "cosmos.schema.md").read_text()
    assert committed == rendered
    assert "/idempotency_key" in committed
    assert "`apply_runs`" in committed

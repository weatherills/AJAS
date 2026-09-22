"""Database PRD kanban: bootstrap, sprocs, migrate, identity, backup, contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.storage.backup import CRITICAL_CONTAINERS, export_backup, import_backup
from app.storage.catalog import container_catalog, container_by_id, render_cosmos_schema
from app.storage.contracts import FE_DB_REVIEW_MATCH, project_review_match
from app.storage.dal import ConflictError, CosmosDAL
from app.storage.entity_dal import catalog_repositories, repository_for
from app.storage.identity import assert_no_plaintext_secrets, resolve_blob_auth, resolve_cosmos_auth, resolve_queue_auth
from app.storage.migrate import apply_migrations, current_schema_version, migration_plan
from app.storage.ops import evaluate_alerts, storage_snapshot
from app.storage.provision import provision_all, provision_cosmos
from app.storage.queue_schemas import QUEUE_SCHEMAS, parse_queue_message
from app.storage.seeds import seed_documents
from app.storage.sprocs import (
    SCHEMA_VERSION,
    StaleVersionError,
    avg_score,
    deploy_stored_logic,
    enqueue_hint_for,
    safe_upsert_document,
    stored_logic_catalog,
)
from app.storage.testing import FakeDatabase

REPO = Path(__file__).resolve().parents[2]


def test_bootstrap_plan_is_idempotent_and_serverless():
    first = provision_all(dry_run=True)
    second = provision_all(dry_run=True)
    assert first["cosmos"] == second["cosmos"]
    assert first["throughput"] == "serverless"
    assert first["schemaVersion"] == SCHEMA_VERSION
    assert "schema_migrations" in first["cosmos"]
    db = FakeDatabase()
    created = provision_cosmos(db)
    again = provision_cosmos(db)
    assert created == again
    assert "matches" in created
    assert any(item["id"] == "schema_migrations" for item in db.created)


def test_container_list_covers_prd_domains_and_schema_doc():
    features = {spec.feature for spec in container_catalog()}
    assert features >= {
        "platform",
        "resumes",
        "job_sources",
        "auto_apply",
        "review",
        "mail",
        "settings",
        "learning",
        "matching",
        "privacy",
    }
    ids = {spec.id for spec in container_catalog()}
    assert {
        "resumes",
        "job_postings_canonical",
        "auto_apply_attempts",
        "matches",
        "email_threads",
        "user_settings",
        "decision_log",
        "job_sources",
        "audit_events",
        "event_log",
    } <= ids
    rendered = render_cosmos_schema()
    committed = (REPO / "docs" / "cosmos.schema.md").read_text()
    assert committed == rendered
    assert container_by_id("schema_migrations").partition_key == "/id"


def test_catalog_dal_crud_etag_and_soft_delete():
    dal = CosmosDAL(FakeDatabase())
    repos = catalog_repositories(dal)
    assert set(repos) == {spec.id for spec in container_catalog()}
    resumes = repository_for(dal, "resumes")
    created = resumes.create(
        {
            "id": "r1",
            "user_id": "u1",
            "original_filename": "cv.pdf",
            "mime_type": "application/pdf",
            "file_size": 12,
            "blob_uri": "u1/r1/cv.pdf",
            "checksum_sha256": "ab",
        }
    )
    assert created["schemaVersion"] == 1
    assert created["_etag"]
    fetched = resumes.get("r1", partition_key="u1")
    with pytest.raises(ConflictError):
        resumes.upsert({"id": "r1", "user_id": "u1", "original_filename": "other.pdf"}, etag="nope")
    updated = resumes.upsert({"id": "r1", "user_id": "u1", "original_filename": "cv2.pdf"}, etag=fetched["_etag"])
    assert updated["schemaVersion"] >= 2
    soft = resumes.soft_delete("r1", partition_key="u1")
    assert soft["is_deleted"] is True
    assert soft["deleted_at"]


def test_stored_logic_versioned_and_deployed_in_bootstrap():
    catalog = stored_logic_catalog()
    assert {item["id"] for item in catalog} == {"sp_safeUpsert", "udf_avgScore", "trg_setTimestamps", "trg_enqueueHint"}
    assert all(item["body"].strip() for item in catalog)
    assert avg_score([70, 90]) == 80
    merged = safe_upsert_document(None, {"id": "m1", "schemaVersion": 0})
    assert merged["schemaVersion"] == 1
    bumped = safe_upsert_document(merged, {"id": "m1", "schemaVersion": 1})
    assert bumped["schemaVersion"] == 2
    with pytest.raises(StaleVersionError):
        safe_upsert_document(bumped, {"id": "m1", "schemaVersion": 1})
    assert enqueue_hint_for("match_runs", {"id": "run-1"})["queue"] == "match-compute"
    db = FakeDatabase()
    apply_migrations(db)
    scripts = db.get_container_client("matches").scripts
    assert "sp_safeUpsert" in scripts.sprocs
    assert "udf_avgScore" in scripts.udfs
    assert "trg_setTimestamps" in scripts.triggers
    assert "trg_enqueueHint" in scripts.triggers


def test_indexing_and_ttl_policies_are_explicit():
    for spec in container_catalog():
        policy = spec.indexing_policy
        assert policy["indexingMode"] == "consistent"
        assert policy["includedPaths"]
        assert any(path.get("path") == '/"_etag"/?' for path in policy["excludedPaths"])
    assert container_by_id("job_postings_raw").default_ttl == 90 * 86_400
    assert container_by_id("matches").default_ttl is None
    assert container_by_id("user_settings").default_ttl is None
    excluded = [item["path"] for item in container_by_id("email_connections").indexing_policy["excludedPaths"]]
    assert "/access_token_enc/?" in excluded


def test_queue_schemas_cover_db_adjacent_pipelines():
    stamp = "2026-01-15T12:00:00+00:00"
    assert set(QUEUE_SCHEMAS) >= {
        "review-enrich",
        "auto-apply-requests",
        "auto-apply-submits",
        "auto-apply-webhooks",
        "match-compute",
        "crawl-runs",
        "job-fetch",
        "resume-parse",
    }
    enrich = parse_queue_message("review-enrich", {"enqueued_at": stamp, "user_id": "u1", "match_id": "m1"})
    assert enrich.kind == "review-enrich"


def test_emulator_compose_env_and_ci_bootstrap():
    compose = (REPO / "docker-compose.yml").read_text()
    assert "azurite" in compose
    assert "azure-cosmos-emulator" in compose
    env = (REPO / ".env.sample").read_text()
    assert "COSMOS_ENDPOINT" in env
    assert "BLOB_ACCOUNT_URL" in env
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    assert "provision_storage.py --dry-run" in ci
    assert "provision_storage.py --blobs --queues" in ci
    assert "--cov-fail-under=80" in ci
    assert (REPO / "docs" / "db-setup.md").is_file()


def test_seeds_cover_resumes_jobs_applications_and_settings():
    docs = seed_documents()
    assert docs["resumes"][0]["user_id"] == docs["users"][0]["id"]
    assert docs["auto_apply_attempts"][0]["job_id"] == docs["job_postings_canonical"][0]["id"]
    assert docs["user_settings"][0]["user_id"] == docs["users"][0]["id"]
    assert docs["job_sources"][0]["id"] == "greenhouse"


def test_migration_runner_records_schema_version():
    db = FakeDatabase()
    result = apply_migrations(db)
    assert result["status"] == "applied"
    assert result["schemaVersion"] == current_schema_version()
    assert migration_plan()[0]["id"] == SCHEMA_VERSION
    row = CosmosDAL(db).read("schema_migrations", SCHEMA_VERSION, partition_key=SCHEMA_VERSION)
    assert row["scriptVersion"] == 1
    second = apply_migrations(db)
    assert second["schemaVersion"] == result["schemaVersion"]


def test_identity_modes_never_echo_secrets():
    conn = Settings(cosmos_connection_string="AccountKey=super-secret;AccountName=x")
    assert resolve_cosmos_auth(conn)["mode"] == "connection_string"
    assert "super-secret" not in resolve_cosmos_auth(conn)["secret"]
    aad = Settings(cosmos_connection_string="", cosmos_endpoint="https://ajas.documents.azure.com:443/")
    assert resolve_cosmos_auth(aad)["mode"] == "aad"
    key = Settings(cosmos_connection_string="", cosmos_endpoint="https://localhost:8081", cosmos_key="emulator")
    assert resolve_cosmos_auth(key)["mode"] == "key"
    blob = Settings(blob_connection_string="", blob_account_url="https://acct.blob.core.windows.net")
    assert resolve_blob_auth(blob)["mode"] == "aad"
    queue = Settings(queue_connection_string="", queue_account_url="https://acct.queue.core.windows.net")
    assert resolve_queue_auth(queue)["mode"] == "aad"
    with pytest.raises(ValueError):
        assert_no_plaintext_secrets({"COSMOS_CONNECTION_STRING": "AccountKey=abc"})


def test_ops_alerts_on_dlq_and_latency():
    snap = storage_snapshot(
        queue_depths={"crawl-runs": 1, "crawl-runs-poison": 2},
        blob_bytes={"resumes": 1},
        ru_per_sec=1,
        latency_ms=300,
    )
    names = {item["metric"] for item in evaluate_alerts(snap)}
    assert "queue.dlq_depth" in names
    assert "cosmos.latency_ms" in names
    assert snap["queues"]["poison"]["crawl-runs-poison"] == 2


def test_backup_export_import_roundtrip(tmp_path):
    dal = CosmosDAL(FakeDatabase())
    dal.upsert("matches", {"id": "m1", "user_id": "u1", "job_title": "Eng", "status": "PENDING"})
    dal.upsert("user_settings", {"id": "u1", "user_id": "u1", "theme": "dark"})
    dest = tmp_path / "backup"
    counts = export_backup(dal, dest, containers=CRITICAL_CONTAINERS)
    assert counts["matches"] == 1
    assert (dest / "matches.jsonl").read_text()
    other = CosmosDAL(FakeDatabase())
    imported = import_backup(other, dest, containers=("matches", "user_settings"))
    assert imported["matches"] == 1
    assert other.read("matches", "m1", partition_key="u1")["job_title"] == "Eng"
    assert "Backup" in (REPO / "docs" / "db-setup.md").read_text()


def test_frontend_review_contract_projects_db_fields():
    row = seed_documents()["matches"][0]
    dto = project_review_match(row)
    for fe_field, db_field in FE_DB_REVIEW_MATCH.items():
        if fe_field in {"etag", "status"}:
            continue
        assert dto[fe_field] == row.get(db_field)
    assert dto["matchId"] == row["id"]
    assert dto["score"] == row["ai_score"]
    assert dto["jobTitle"] == row["job_title"]
    assert dto["status"] == "pending"


def test_docs_cover_bootstrap_and_failure_modes():
    text = (REPO / "docs" / "db-setup.md").read_text()
    readme = (REPO / "README.md").read_text()
    assert "provision_storage.py" in text
    assert "migrate_storage.py" in text
    assert "429" in text
    assert "docs/db-setup.md" in readme
    assert deploy_stored_logic(FakeDatabase(), containers=["matches"])["scripts"]

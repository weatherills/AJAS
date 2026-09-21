"""Database Bootstrap epic: 25 Kanban tasks + auto-create missing Cosmos DB."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.features.health import ready
from app.storage.bootstrap import bootstrap_on_startup, ensure_cosmos_database, is_not_found, reset_bootstrap_state
from app.storage.catalog import container_by_id, container_catalog, render_cosmos_schema
from app.storage.dal import CosmosDAL
from app.storage.entity_dal import repository_for
from app.storage.epic import (
    KANBAN_CONTAINERS,
    LEARNING_EVENT_SCHEMA,
    METRICS_SNAPSHOT_SCHEMA,
    SETTINGS_DEFAULTS,
    catalog_covers_epic,
    composite_paths,
    persist_saved,
    physical_containers,
    resolve_container,
    settings_document,
    unique_key_paths,
)
from app.storage.pii import redact
from app.storage.provision import provision_cosmos
from app.storage.seeds import apply_seed, seed_documents
from app.storage.testing import FakeDatabase
from app.storage.versions import mark_removed, version_document

REPO = Path(__file__).resolve().parents[2]


class _MissingDatabaseAccount:
    def __init__(self) -> None:
        self.created = False
        self.db = FakeDatabase()

    def get_database_client(self, name: str):
        if self.created:
            return self.db

        account = self

        class _Missing:
            def read(self) -> None:
                error = Exception("NotFound (404): Database 'ajas' is not found")
                error.status_code = 404  # type: ignore[attr-defined]
                raise error

        return _Missing()

    def create_database_if_not_exists(self, id: str):  # noqa: A002
        self.created = True
        self.db.created.append({"id": id, "kind": "database"})
        return self.db


def _req(method: str = "GET"):
    import azure.functions as func

    return func.HttpRequest(method=method, url="http://localhost/api/ready", body=b"", headers={})


def test_review_decisions_and_reviews_history_containers():
    assert resolve_container("decisions") == "decision_events"
    assert resolve_container("reviews_history") == "audit_events"
    assert container_by_id("decision_events").partition_key == "/user_id"
    assert container_by_id("audit_events").partition_key == "/user_id"


def test_decisions_unique_job_and_created_at_index():
    spec = container_by_id("decision_events")
    assert "job_id" in spec.logical_unique
    composites = composite_paths("decision_events")
    assert ["/user_id", "/created_at"] in composites
    assert any("/job_id" in path for path in composites)


def test_seed_decisions_and_history():
    docs = seed_documents()
    assert docs["decision_events"][0]["job_id"] == docs["matches"][0]["job_id"]
    assert docs["audit_events"][0]["event_type"] == "DECISION_RECORDED"


def test_applications_and_application_events_containers():
    assert resolve_container("applications") == "auto_apply_attempts"
    assert resolve_container("application_events") == "status_events"
    assert container_by_id("auto_apply_attempts").partition_key == "/user_id"
    assert container_by_id("status_events").partition_key == "/auto_apply_id"


def test_application_idempotency_and_status_indexes():
    assert unique_key_paths("auto_apply_attempts") == [("/job_id", "/resume_id")]
    spec = container_by_id("auto_apply_attempts")
    assert spec.logical_unique == ("user_id", "job_id", "resume_id")
    composites = composite_paths("auto_apply_attempts")
    assert ["/user_id", "/status", "/updated_at"] in composites


def test_seed_applications_and_events():
    docs = seed_documents()
    app = docs["auto_apply_attempts"][0]
    events = docs["status_events"]
    assert app["status"] == "submitted"
    assert {row["event_type"] for row in events} >= {"created", "queued", "submission_succeeded"}
    assert all(row["auto_apply_id"] == app["id"] for row in events)


def test_user_settings_container():
    spec = container_by_id("user_settings")
    assert spec.partition_key == "/user_id"
    assert spec.id == resolve_container("user_settings")


def test_settings_schema_and_defaults():
    assert SETTINGS_DEFAULTS["matchThreshold"] == 70
    assert SETTINGS_DEFAULTS["sourceToggles"]["greenhouse"] is True
    doc = settings_document("u1")
    assert doc["match_threshold"] == 70
    assert doc["email_connection"]["provider"] == "microsoft_365"


def test_seed_example_user_settings():
    rows = seed_documents()["user_settings"]
    by_id = {row["id"]: row for row in rows}
    assert by_id["seed-user-001"]["match_threshold"] == 70
    assert by_id["seed-user-strict"]["match_threshold"] == 90
    assert by_id["seed-user-strict"]["lever_enabled"] is False


def test_resumes_and_resume_versions_containers():
    assert resolve_container("resumes") == "resumes"
    assert resolve_container("resume_versions") == "resume_versions"
    assert container_by_id("resumes").partition_key == "/user_id"
    assert container_by_id("resume_versions").partition_key == "/resume_id"


def test_resume_blob_metadata_soft_delete_and_ttl():
    row = version_document(
        version_id="v1",
        resume_id="r1",
        user_id="u1",
        version=1,
        blob_uri="u1/r1/cv.pdf",
        original_filename="cv.pdf",
        checksum_sha256="ab",
    )
    assert row["blob_uri"].endswith("cv.pdf")
    removed = mark_removed(row)
    assert removed["is_deleted"] is True
    assert removed["ttl"] == 90 * 86_400
    dal = CosmosDAL(FakeDatabase())
    provision_cosmos(dal._database)  # type: ignore[attr-defined]
    repo = repository_for(dal, "resume_versions")
    created = repo.create(row)
    soft = repo.soft_delete(created["id"], partition_key=created["resume_id"])
    assert soft["is_deleted"] is True
    assert soft["ttl"] == 90 * 86_400


def test_seed_resumes_and_versions():
    docs = seed_documents()
    versions = docs["resume_versions"]
    assert len(versions) == 2
    assert {row["version"] for row in versions} == {1, 2}
    assert any(row["is_deleted"] for row in versions)
    assert docs["resumes"][0]["id"] == versions[0]["resume_id"]


def test_job_postings_and_crawls_containers():
    assert resolve_container("job_postings") == "job_postings_canonical"
    assert resolve_container("crawls") == "source_fetch_runs"
    assert container_by_id("job_postings_canonical").partition_key == "/id"
    assert container_by_id("source_fetch_runs").partition_key == "/source_tenant_id"


def test_job_dedupe_and_filter_indexes():
    spec = container_by_id("job_postings_canonical")
    assert "company+apply_url" in spec.logical_unique
    composites = composite_paths("job_postings_canonical")
    assert ["/company", "/posted_at"] in composites
    assert ["/location"] in composites
    assert ["/source"] in composites


def test_seed_greenhouse_and_lever_postings():
    docs = seed_documents()
    sources = {row["id"] for row in docs["job_sources"]}
    assert sources == {"greenhouse", "lever"}
    companies = {row["company"] for row in docs["job_postings_canonical"]}
    assert companies == {"Acme", "Beta"}
    assert docs["source_fetch_runs"][0]["status"] == "succeeded"


def test_matches_container():
    spec = container_by_id("matches")
    assert spec.partition_key == "/user_id"
    assert spec.unique_keys == (("/job_id", "/resume_id"),)


def test_match_composites_and_threshold_persistence():
    composites = composite_paths("matches")
    assert ["/job_id", "/resume_id"] in composites
    assert any(path[:2] == ["/user_id", "/ai_score"] for path in composites)
    assert persist_saved(score=0.91, threshold=70) is True
    assert persist_saved(score=0.41, threshold=70) is False
    docs = seed_documents()["matches"]
    by_id = {row["id"]: row for row in docs}
    assert by_id["seed-match-001"]["saved"] is True
    assert by_id["seed-match-low"]["saved"] is False


def test_seed_matches_across_thresholds():
    scores = sorted(row["ai_score"] for row in seed_documents()["matches"])
    assert scores[0] < 0.7 <= scores[-1]


def test_email_threads_and_messages_containers():
    assert resolve_container("email_threads") == "email_threads"
    assert resolve_container("email_messages") == "email_messages"
    assert container_by_id("email_threads").partition_key == "/email_account_id"
    assert container_by_id("email_messages").partition_key == "/email_account_id"


def test_email_pii_body_hash_and_indexes():
    composites = composite_paths("email_messages")
    assert ["/email_thread_id", "/received_at"] in composites
    assert ["/graph_message_id"] in composites
    msg = seed_documents()["email_messages"][0]
    assert msg["body_hash"]
    redacted = redact("email_messages", msg)
    assert "recruiter@acme.test" not in str(redacted.get("from_address"))
    assert redacted["body_text"] != msg["body_text"] or "***" in str(redacted["body_text"])


def test_seed_threads_messages_attachments():
    docs = seed_documents()
    assert docs["email_messages"][0]["email_thread_id"] == docs["email_threads"][0]["id"]
    assert docs["email_attachments"][0]["filename"] == "jd.pdf"


def test_learning_events_and_metrics_containers():
    assert resolve_container("learning_events") == "decision_log"
    assert resolve_container("metrics_snapshots") == "metrics_snapshot"
    assert container_by_id("decision_log").partition_key == "/user_id"
    assert container_by_id("metrics_snapshot").partition_key == "/scope_ref"


def test_learning_event_and_snapshot_schema():
    assert LEARNING_EVENT_SCHEMA["decision"] == "approve | reject | skip"
    assert "precision" in METRICS_SNAPSHOT_SCHEMA
    assert "recall" in METRICS_SNAPSHOT_SCHEMA
    event = seed_documents()["decision_log"][0]
    snap = seed_documents()["metrics_snapshot"][0]
    assert event["decision"] == "approve"
    assert 0 <= snap["precision"] <= 1
    assert 0 <= snap["recall"] <= 1


def test_seed_learning_events_and_snapshots():
    dal = CosmosDAL(FakeDatabase())
    counts = apply_seed(dal)
    assert counts["decision_log"] == 1
    assert counts["metrics_snapshot"] == 1
    page = dal.query("decision_log", "SELECT * FROM c", partition_key="seed-user-001")
    assert page.items[0]["match_id"] == "seed-match-001"


def test_epic_bootstrap_maps_every_kanban_container_and_docs():
    assert catalog_covers_epic() == []
    assert set(physical_containers()) == set(KANBAN_CONTAINERS)
    rendered = render_cosmos_schema()
    committed = (REPO / "docs" / "cosmos.schema.md").read_text()
    assert committed == rendered
    assert "resume_versions" in committed
    text = (REPO / "backend" / "function_app.py").read_text()
    assert "bootstrap_on_startup" in text
    assert "run_on_startup=True" in text


def test_auto_bootstrap_creates_database_when_missing():
    reset_bootstrap_state()
    account = _MissingDatabaseAccount()
    db = ensure_cosmos_database(client=account, seed=True)
    assert account.created is True
    ids = {spec.id for spec in container_catalog()}
    provisioned = {item["id"] for item in account.db.created if "id" in item}
    assert "matches" in ids
    assert "resume_versions" in ids
    # Seeded after create
    matches = CosmosDAL(db).query("matches", "SELECT * FROM c", partition_key="seed-user-001")
    assert {row["id"] for row in matches.items} >= {"seed-match-001", "seed-match-low"}
    again = ensure_cosmos_database(client=account, seed=True)
    assert again is db


def test_bootstrap_on_startup_skips_when_cosmos_unconfigured():
    reset_bootstrap_state()
    skipped = bootstrap_on_startup()
    assert skipped["status"] == "skipped"
    assert skipped["bootstrapped"] is False
    resp = ready(_req())
    import json

    body = json.loads(resp.get_body())
    assert body["ready"] is True
    assert body["cosmosBootstrap"]["status"] == "skipped"


def test_bootstrap_on_startup_reports_error_without_raising():
    reset_bootstrap_state()

    class _Boom:
        def get_database_client(self, name: str):
            raise RuntimeError("account unreachable")

    result = bootstrap_on_startup(client=_Boom())
    assert result["status"] == "error"
    assert result["bootstrapped"] is False
    assert "unreachable" in result["error"]
    error = Exception("NotFound")
    error.status_code = 404  # type: ignore[attr-defined]
    assert is_not_found(error) is True
    assert is_not_found(ValueError("nope")) is False

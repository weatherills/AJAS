"""Database PRD catalog: core entities, partition keys, uniqueness, TTL, indexes."""

from __future__ import annotations

from app.storage.catalog import (
    container_catalog,
    container_by_id,
    core_container_ids,
    indexing_report,
    ttl_containers,
    user_scoped_containers,
)
from app.storage.entities import (
    CORE_ENTITIES,
    Application,
    EventLog,
    JobPosting,
    MailThread,
    StoredResume,
    User,
)


def test_core_entities_are_the_six_named_in_the_kanban_task():
    assert set(CORE_ENTITIES) == {"User", "JobPosting", "Resume", "Application", "MailThread", "EventLog"}
    assert core_container_ids() == (
        "users",
        "job_postings_canonical",
        "resumes",
        "auto_apply_attempts",
        "email_threads",
        "event_log",
    )
    for name, meta in CORE_ENTITIES.items():
        assert meta["partition_key"].startswith("/")
        assert meta["query_patterns"]
        assert meta["relationships"]
        assert meta["container"]
        assert meta["model"] in {User, JobPosting, StoredResume, Application, MailThread, EventLog}


def test_catalog_covers_every_database_prd_feature():
    features = {spec.feature for spec in container_catalog()}
    assert features >= {
        "platform",
        "review",
        "matching",
        "settings",
        "resumes",
        "job_sources",
        "mail",
        "learning",
        "auto_apply",
        "privacy",
        "schema_plane",
    }
    ids = {spec.id for spec in container_catalog()}
    assert "matches" in ids
    assert "job_postings_raw" in ids
    assert "decision_log" in ids
    assert "users" in ids
    assert "event_log" in ids
    assert len(ids) >= 40


def test_partition_keys_match_query_patterns():
    assert container_by_id("matches").partition_key == "/user_id"
    assert container_by_id("decision_events").partition_key == "/user_id"
    assert container_by_id("audit_events").partition_key == "/user_id"
    assert container_by_id("resumes").partition_key == "/user_id"
    assert container_by_id("auto_apply_attempts").partition_key == "/user_id"
    assert container_by_id("email_threads").partition_key == "/email_account_id"
    assert container_by_id("job_postings_raw").partition_key == "/source_tenant_id"
    assert container_by_id("match_explanations").partition_key == "/match_id"
    assert container_by_id("users").partition_key == "/id"
    scoped = {spec.id for spec in user_scoped_containers()}
    assert "matches" in scoped
    assert "resumes" in scoped
    assert "event_log" in scoped
    assert "users" not in scoped


def test_uniqueness_policies_omit_partition_key():
    runs = container_by_id("match_runs")
    assert runs.unique_keys == (("/idempotency_key",),)
    assert "user_id" in runs.logical_unique
    tenants = container_by_id("source_tenants")
    assert tenants.unique_keys == (("/tenant_key",),)
    messages = container_by_id("email_messages")
    assert messages.unique_keys == (("/graph_message_id",),)
    matches = container_by_id("matches")
    assert matches.unique_keys == (("/job_id", "/resume_id"),)
    for spec in container_catalog():
        pk = spec.partition_key
        for paths in spec.unique_keys:
            assert pk not in paths
            assert pk.lstrip("/") not in {path.lstrip("/") for path in paths}


def test_ttl_only_on_transient_payloads():
    ttl = {spec.id: spec.default_ttl for spec in ttl_containers()}
    assert ttl["job_postings_raw"] == 90 * 86_400
    assert ttl["fetch_requests"] == 30 * 86_400
    assert ttl["email_ingestion_events"] == 30 * 86_400
    assert ttl["webhook_callbacks"] == 90 * 86_400
    assert ttl["event_log"] == 30 * 86_400
    assert container_by_id("matches").default_ttl is None
    assert container_by_id("resumes").default_ttl is None
    assert container_by_id("settings_audit_log").default_ttl is None
    assert container_by_id("status_events").default_ttl is None


def test_indexing_policies_include_hot_composites_and_ru_notes():
    matches = container_by_id("matches")
    composites = matches.indexing_policy["compositeIndexes"]
    paths = [[part["path"] for part in index] for index in composites]
    assert ["/user_id", "/status", "/queued_at"] in paths
    connections = container_by_id("email_connections")
    excluded = [item["path"] for item in connections.indexing_policy["excludedPaths"]]
    assert "/access_token_enc/?" in excluded
    report = indexing_report()
    by_id = {row["id"]: row for row in report}
    assert by_id["matches"]["composite_count"] >= 3
    assert by_id["job_postings_raw"]["ru_note"]
    assert all(row["ru_note"] for row in report)

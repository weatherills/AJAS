"""Matching records plane, compliance contracts, and remaining Cosmos todos."""

from __future__ import annotations

import hashlib
import json
import os

import azure.functions as func
import pytest

from app.compliance import (
    append_audit,
    data_map,
    dpa_bundle,
    evidence_map,
    reset_audit_chain,
    soc2_inventory,
    subprocessors,
    verify_audit_chain,
)
from app.config import get_settings
from app.features import matching as routes
from app.features.ops import ops_compliance, ops_compliance_audit
from app.features.privacy import privacy_requests
from app.matching.constants import (
    DEFAULT_PRUNE_KEEP,
    EVIDENCE_CONTAINER,
    EVIDENCE_INDEXING,
    EVIDENCE_PK,
    EVIDENCE_TTL_DAYS,
    EVIDENCE_TTL_SECONDS,
    RECORDS_CONTAINER,
    RECORDS_INDEXING,
    RECORDS_PK,
)
from app.matching.containers import container_specs, ensure_matching_containers
from app.matching.errors import MatchingValidationError
from app.matching.records import (
    MatchRecordStore,
    get_record_store,
    match_record_id,
    reset_record_store,
    select_keep,
)
from app.privacy import container_specs as privacy_specs, reset_privacy_requests
from app.storage.catalog import container_by_id, container_catalog
from app.storage.dal import ConflictError, CosmosDAL
from app.storage.entity_dal import catalog_repositories
from app.storage.epic import catalog_covers_epic, resolve_container
from app.storage.provision import provision_cosmos
from app.storage.retention import execute_gdpr_delete, gdpr_plan
from app.storage.testing import FakeDatabase


USER = "user-1"


def _req(
    method: str,
    url: str,
    *,
    user: str | None = USER,
    json_body=None,
    params: dict | None = None,
    route: dict | None = None,
    raw: bytes | None = None,
) -> func.HttpRequest:
    hdrs: dict[str, str] = {}
    body = raw if raw is not None else b""
    if user:
        hdrs["Authorization"] = f"Bearer {user}"
    if json_body is not None:
        hdrs["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode()
    return func.HttpRequest(
        method=method,
        url=url,
        headers=hdrs,
        params=params or {},
        route_params=route or {},
        body=body,
    )


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    return json.loads(raw) if raw else None


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    reset_record_store()
    reset_audit_chain()
    reset_privacy_requests()
    yield
    reset_record_store()
    reset_audit_chain()
    reset_privacy_requests()
    get_settings.cache_clear()


def test_match_records_and_evidence_containers_and_indexes():
    specs = {item["id"]: item for item in container_specs()}
    assert specs[RECORDS_CONTAINER]["partition_key"] == RECORDS_PK == "/userId"
    assert specs[EVIDENCE_CONTAINER]["partition_key"] == EVIDENCE_PK == "/userId"
    record_paths = [[part["path"] for part in index] for index in RECORDS_INDEXING["compositeIndexes"]]
    assert ["/userId", "/jobId"] in record_paths
    assert ["/userId", "/createdAt"] in record_paths
    evidence_paths = [[part["path"] for part in index] for index in EVIDENCE_INDEXING["compositeIndexes"]]
    assert ["/userId", "/matchId", "/createdAt"] in evidence_paths
    catalog_records = container_by_id("match_records")
    catalog_evidence = container_by_id("match_evidence")
    assert catalog_records.partition_key == "/userId"
    assert catalog_evidence.default_ttl == EVIDENCE_TTL_SECONDS
    assert catalog_evidence.default_ttl == 180 * 86_400
    db = FakeDatabase()
    ensure_matching_containers(db)
    created = {item["id"] for item in db.created}
    assert {RECORDS_CONTAINER, EVIDENCE_CONTAINER} <= created


def test_deterministic_match_record_id_is_sha256_of_tuple():
    first = match_record_id(user_id="u", job_id="j", resume_id="r", model_version="matching-v1")
    again = match_record_id(user_id="u", job_id="j", resume_id="r", model_version="matching-v1")
    other = match_record_id(user_id="u", job_id="j", resume_id="r", model_version="matching-v2")
    expected = hashlib.sha256(b"u|j|r|matching-v1").hexdigest()
    assert first == again == expected
    assert other != first
    resp = routes.match_record_id_preview(_req("GET", "http://localhost/api/v1/matching/id", params={"jobId": "j", "resumeId": "r"}))
    assert resp.status_code == 200
    assert _body(resp)["id"] == match_record_id(user_id=USER, job_id="j", resume_id="r", model_version="matching-v1")


def test_etag_upsert_creates_then_conflicts_then_replaces():
    store = get_record_store()
    created = store.upsert_score(user_id=USER, job_id="job-a", resume_id="resume-a", score=70)
    assert created["status"] == "created"
    etag = created["record"]["_etag"]
    with pytest.raises(ConflictError):
        store.upsert_score(user_id=USER, job_id="job-a", resume_id="resume-a", score=71, etag="stale")
    updated = store.upsert_score(user_id=USER, job_id="job-a", resume_id="resume-a", score=88, etag=etag)
    assert updated["status"] == "updated"
    assert updated["record"]["score"] == 88
    assert updated["record"]["_etag"] != etag


def test_select_keep_latest_five_ties_and_missing_timestamps():
    rows = []
    for index in range(8):
        rows.append({"id": f"v{index:02d}", "jobId": "j", "resumeId": "r", "modelVersion": "matching-v1", "createdAt": f"2026-01-0{index + 1}T00:00:00Z"})
    rows.append({"id": "tie-a", "jobId": "j", "resumeId": "r", "modelVersion": "matching-v1", "createdAt": "2026-02-01T00:00:00Z"})
    rows.append({"id": "tie-b", "jobId": "j", "resumeId": "r", "modelVersion": "matching-v1", "createdAt": "2026-02-01T00:00:00Z"})
    rows.append({"id": "no-ts", "jobId": "j", "resumeId": "r", "modelVersion": "matching-v1"})
    plan = select_keep(rows, keep=5)
    retained_ids = {row["id"] for row in plan["retain"]}
    deleted_ids = {row["id"] for row in plan["delete"]}
    assert plan["keep"] == 5
    assert "no-ts" in deleted_ids
    assert "tie-b" in retained_ids
    assert "v00" in deleted_ids
    assert len(plan["retain"]) == 5


def test_prune_keep_five_dry_run_and_apply():
    store = get_record_store()
    for index in range(8):
        store.upsert_score(
            user_id=USER,
            job_id="job-keep",
            resume_id="resume-keep",
            score=50 + index,
            created_at=f"2026-03-{index + 1:02d}T00:00:00Z",
        )
    dry = store.prune(USER, keep=DEFAULT_PRUNE_KEEP, dry_run=True)
    assert dry["dryRun"] is True
    assert dry["deleted"] == 0
    assert len(dry["wouldDelete"]) == 3
    assert len(store.list_records(USER, latest_only=False)) == 9  # 1 current + 8 versions
    applied = store.prune(USER, keep=5, dry_run=False)
    assert applied["deleted"] == 3
    remaining_versions = [row for row in store.list_records(USER, latest_only=False) if not row.get("latest")]
    assert len(remaining_versions) == 5
    latest = store.list_records(USER)
    assert len(latest) == 1
    assert latest[0]["latest"] is True


def test_evidence_ttl_is_180_days_and_telemetry_emits():
    store = get_record_store()
    saved = store.upsert_score(
        user_id=USER,
        job_id="job-e",
        resume_id="resume-e",
        score=91,
        evidence=["Python on Azure Functions.", "Cosmos composite indexes."],
    )
    assert saved["evidence"]["ttl"] == EVIDENCE_TTL_SECONDS
    assert EVIDENCE_TTL_DAYS == 180
    rows = store.list_evidence(USER, saved["record"]["id"])
    assert rows[0]["ttl"] == 180 * 86_400
    events = {item["event"] for item in store.telemetry}
    assert "score" in events
    assert any(item.get("latencyMs", 0) >= 0 and item.get("correlationId") for item in store.telemetry)


def test_batch_rescore_and_http_surface():
    created = routes.match_records(
        _req("POST", "http://localhost/api/v1/match-records", json_body={"jobId": "job-1", "resumeId": "cv-1", "score": 77, "evidence": [" overlap "]})
    )
    assert created.status_code == 201
    listed = routes.match_records(_req("GET", "http://localhost/api/v1/match-records"))
    items = _body(listed)["items"]
    assert items[0]["jobId"] == "job-1"
    match_id = items[0]["id"]
    detail = routes.match_record_detail(
        _req("GET", f"http://localhost/api/v1/match-records/{match_id}", route={"matchId": match_id})
    )
    assert _body(detail)["evidence"]
    rescore = routes.match_record_rescore(
        _req("POST", f"http://localhost/api/v1/match-records/{match_id}/rescore", route={"matchId": match_id}, json_body={"score": 82})
    )
    assert rescore.status_code == 200
    assert _body(rescore)["record"]["score"] == 82
    batch = routes.match_records_batch(
        _req(
            "POST",
            "http://localhost/api/v1/matching/batch-rescore",
            json_body={"pairs": [{"jobId": "job-2", "resumeId": "cv-1", "score": 60}, {"jobId": "job-3", "resumeId": "cv-1", "score": 95}]},
        )
    )
    assert _body(batch)["count"] == 2
    prune = routes.match_records_prune(_req("POST", "http://localhost/api/v1/matching/prune", json_body={"dryRun": True, "keep": 5}))
    assert _body(prune)["dryRun"] is True
    tel = routes.match_records_telemetry(_req("GET", "http://localhost/api/v1/matching/telemetry"))
    assert _body(tel)["count"] >= 1
    missing = routes.match_records(_req("POST", "http://localhost/api/v1/match-records", json_body={"score": 1}))
    assert missing.status_code == 400


def test_etag_conflict_returns_409():
    store = get_record_store()
    store.upsert_score(user_id=USER, job_id="job-x", resume_id="resume-x", score=10)
    conflict = routes.match_records(
        _req("POST", "http://localhost/api/v1/match-records", json_body={"jobId": "job-x", "resumeId": "resume-x", "score": 11, "etag": "nope"})
    )
    assert conflict.status_code == 409


def test_soc2_dpa_subprocessors_and_tamper_evident_audit():
    inventory = soc2_inventory()
    ids = {row["id"] for row in inventory["controls"]}
    assert {"CC6.1", "CC6.6", "CC7.2", "A1.2", "C1.1", "CC8.1"} <= ids
    assert inventory["ownership"]["CC6.1"]["owner"] == "platform"
    assert inventory["gaps"]
    assert evidence_map()["cadence"] == "quarterly evidence pull"
    names = {row["name"] for row in subprocessors()["items"]}
    assert "Azure Cosmos DB" in names
    bundle = dpa_bundle()
    assert "processor" in bundle["template"].lower()
    assert any(row["container"] == "match_records" for row in bundle["dataMap"])
    assert data_map()
    reset_audit_chain()
    first = append_audit("login", {"user": "ada"})
    second = append_audit("export", {"container": "resumes"})
    assert verify_audit_chain() == {"ok": True, "length": 2}
    broken = [dict(first), dict(second)]
    broken[1]["hash"] = "tampered"
    assert verify_audit_chain(broken)["ok"] is False
    req = _req("GET", "http://localhost/api/v1/ops/compliance", user="local-admin")
    body = _body(ops_compliance(req))
    assert body["soc2"]["controls"]
    assert body["dpa"]["template"]
    posted = ops_compliance_audit(_req("POST", "http://localhost/api/v1/ops/compliance/audit", user="local-admin", json_body={"action": "review", "payload": {"ok": True}}))
    assert posted.status_code == 201
    assert _body(posted)["chain"]["ok"] is True


def test_privacy_containers_requests_and_gdpr_uses_spec_pk():
    ids = {item["id"] for item in privacy_specs()}
    assert ids >= {
        "data_subjects",
        "privacy_requests",
        "export_bundles",
        "retention_policies",
        "retention_jobs",
        "legal_holds",
        "pii_field_catalog",
        "privacy_audit_log",
    }
    catalog_ids = {spec.id for spec in container_catalog()}
    assert ids <= catalog_ids
    assert container_by_id("privacy_requests").partition_key == "/userId"
    assert container_by_id("export_bundles").default_ttl == 7 * 86_400
    created = privacy_requests(_req("POST", "http://localhost/api/v1/privacy/requests", json_body={"kind": "delete"}))
    assert created.status_code == 201
    listed = privacy_requests(_req("GET", "http://localhost/api/v1/privacy/requests"))
    assert _body(listed)["count"] == 1
    plan = gdpr_plan(USER)
    assert "match_records" in plan["containers"]
    assert "privacy_requests" in plan["containers"]

    class _Store:
        def __init__(self) -> None:
            self.deleted: list[tuple[str, str, str]] = []

        def list_user_documents(self, container: str, user_id: str):
            return [{"id": f"{container}-1", "userId": user_id}]

        def delete_document(self, container: str, item_id: str, partition_key):
            self.deleted.append((container, item_id, partition_key))

        def write_event(self, body: dict) -> None:
            self.event = body

        def delete_blobs(self, container: str, prefix: str) -> int:
            return 0

    store = _Store()
    execute_gdpr_delete(store, USER)
    match_delete = next(item for item in store.deleted if item[0] == "match_records")
    assert match_delete[2] == USER


def test_remaining_cosmos_todos_aliases_dao_ttl_and_learning():
    assert catalog_covers_epic() == []
    assert resolve_container("review_queue") == "matches"
    assert resolve_container("email_threads") == "email_threads"
    assert resolve_container("resume_files") == "resume_versions"
    assert resolve_container("ingestion_jobs") == "source_fetch_runs"
    assert resolve_container("decision_feedback") == "decision_log"
    assert resolve_container("source_toggles") == "source_toggles"
    assert resolve_container("apply_runs") == "apply_runs"
    ids = {spec.id for spec in container_catalog()}
    assert {
        "email_threads",
        "email_messages",
        "email_attachments",
        "resumes",
        "resume_versions",
        "match_records",
        "match_evidence",
        "matches",
        "decision_log",
        "source_toggles",
        "user_settings",
        "job_postings_canonical",
        "source_fetch_runs",
        "auto_apply_attempts",
        "apply_runs",
    } <= ids
    assert container_by_id("auto_apply_attempts").default_ttl == 180 * 86_400
    dal = CosmosDAL(FakeDatabase())
    repos = catalog_repositories(dal)
    assert "match_records" in repos
    assert "privacy_requests" in repos
    row = repos["match_records"].create({"id": "m1", "userId": USER, "jobId": "j", "resumeId": "r", "score": 1})
    fetched = repos["match_records"].get("m1", partition_key=USER)
    assert fetched["id"] == row["id"]
    with pytest.raises(ConflictError):
        repos["match_records"].upsert({"id": "m1", "userId": USER, "score": 2}, etag="nope")


@pytest.mark.emulator
def test_match_records_emulator_or_fake_roundtrip():
    conn = os.environ.get("COSMOS_CONNECTION_STRING") or ""
    if conn:
        from azure.cosmos import CosmosClient

        from app.storage.catalog import ensure_all_containers

        client = CosmosClient.from_connection_string(conn)
        database = client.create_database_if_not_exists(id="ajas-matching-test")
        ensure_all_containers(database)
        dal = CosmosDAL(database)
    else:
        database = FakeDatabase()
        provision_cosmos(database)
        dal = CosmosDAL(database)
    store = MatchRecordStore(dal=dal)
    saved = store.upsert_score(user_id=USER, job_id="emu-job", resume_id="emu-cv", score=64, evidence=["emulator path"])
    loaded = store.get(USER, saved["record"]["id"])
    assert loaded["score"] == 64
    assert store.list_evidence(USER, saved["record"]["id"])
    dry = store.prune(USER, keep=5, dry_run=True)
    assert dry["dryRun"] is True


def test_matching_admin_script_lists_containers_and_prunes(capsys):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "matching_admin.py"
    spec = importlib.util.spec_from_file_location("matching_admin", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    assert mod.main(["containers"]) == 0
    out = capsys.readouterr().out
    assert "match_records" in out
    assert mod.main(["prune", "--user", USER, "--dry-run"]) == 0


def test_upsert_rejects_blank_ids():
    with pytest.raises(MatchingValidationError):
        get_record_store().upsert_score(user_id=USER, job_id="", resume_id="r", score=1)

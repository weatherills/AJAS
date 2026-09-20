"""Seed utilities, ops alerts, retention/GDPR, and CI coverage gate."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import azure.functions as func

from app.metrics import increment, reset
from app.privacy import apply_purge, purge_plan
from app.storage.ops import ALERT_THRESHOLDS, dashboard, evaluate_alerts, storage_snapshot
from app.storage.retention import RETENTION_DAYS, execute_gdpr_delete, gdpr_plan, retention_plan
from app.storage.seeds import SEED_USER_ID, apply_seed, seed_documents
from app.storage.testing import FakeDatabase, MemoryDocumentStore
from app.storage.dal import CosmosDAL


def test_seed_documents_are_deterministic():
    first = seed_documents()
    second = seed_documents()
    assert first == second
    assert first["users"][0]["id"] == SEED_USER_ID
    assert first["resumes"][0]["user_id"] == SEED_USER_ID
    assert first["auto_apply_attempts"][0]["job_id"] == first["job_postings_canonical"][0]["id"]
    dal = CosmosDAL(FakeDatabase())
    counts = apply_seed(dal)
    assert counts["matches"] == 1
    again = apply_seed(dal)
    assert again == counts


def test_ops_metrics_fire_alerts_at_thresholds():
    reset()
    increment("cosmos.ru", 5000)
    increment("cosmos.throttles", 6)
    snap = storage_snapshot(queue_depths={"crawl-runs": 501}, blob_bytes={"resumes": 1}, ru_per_sec=5000)
    alerts = evaluate_alerts(snap)
    names = {item["metric"] for item in alerts}
    assert "cosmos.ru_per_sec" in names
    assert "cosmos.throttles" in names
    assert "queue.depth" in names
    reset()
    quiet = storage_snapshot(queue_depths={"crawl-runs": 1}, blob_bytes={"resumes": 1}, ru_per_sec=1)
    assert evaluate_alerts(quiet) == []
    board = dashboard()
    assert board["snapshot"]["schema"] == "ajas.storage.ops.v1"
    assert ALERT_THRESHOLDS["blob.bytes"] == float(50 * 1024 * 1024 * 1024)


def test_ops_storage_endpoint_is_admin_only():
    from app.features.ops import ops_storage

    def _req(role: str | None) -> func.HttpRequest:
        headers = {"Authorization": "Bearer local-user"}
        if role:
            headers["X-Role"] = role
        return func.HttpRequest(
            method="GET",
            url="http://localhost/api/v1/ops/storage",
            headers=headers,
            params={},
            body=b"",
        )

    denied = ops_storage(_req(None))
    assert denied.status_code == 403
    allowed = ops_storage(_req("admin"))
    assert allowed.status_code == 200
    import json

    body = json.loads(allowed.get_body())
    assert "snapshot" in body
    assert "alerts" in body


def test_retention_and_gdpr_delete_write_audit():
    now = datetime(2026, 9, 20, tzinfo=timezone.utc)
    old = (now - timedelta(days=400)).isoformat()
    plan = retention_plan(
        jobs=[{"id": "j1", "updated_at": old}],
        emails=[{"id": "e1", "received_at": old}],
        matches=[{"id": "m1", "queued_at": old}],
        resumes=[{"id": "r1", "updated_at": old, "user_id": "ada"}],
        applications=[{"id": "a1", "updated_at": old}],
        now=now,
    )
    assert "j1" in plan["jobIds"]
    assert "e1" in plan["emailIds"]
    assert "m1" in plan["matchIds"]
    assert plan["days"]["applications"] == RETENTION_DAYS["applications"]

    store = MemoryDocumentStore()
    store.docs["matches"].append({"id": "m-live", "user_id": "ada", "status": "PENDING"})
    store.docs["resumes"].append({"id": "r-live", "user_id": "ada"})
    store.docs["settings_audit_log"].append({"id": "audit-1", "user_id": "ada"})
    store.blobs["resumes"]["ada/r-live/cv.pdf"] = b"%PDF"
    store.blobs["resumes"]["other/x.pdf"] = b"nope"
    gdpr = execute_gdpr_delete(store, "ada", now=now)
    assert gdpr["status"] == "purged"
    assert gdpr["deletedDocs"] >= 2
    assert gdpr["deletedBlobs"] == 1
    assert store.blobs["resumes"].get("other/x.pdf") == b"nope"
    assert not store.list_user_documents("matches", "ada")
    assert store.docs["settings_audit_log"]  # retained
    assert store.events[0]["event_type"] == "GDPR_DELETE"
    assert "settings_audit_log" in gdpr_plan("ada")["retain"]

    privacy_plan = purge_plan(
        user_id="ada",
        jobs=[{"id": "j1", "user_id": "ada"}],
        emails=[{"id": "e1", "user_id": "ada"}],
        matches=[{"id": "m1", "user_id": "ada"}],
    )
    result = apply_purge(privacy_plan)
    assert result["status"] == "purged"
    assert result["deleted"] == 3
    store2 = MemoryDocumentStore()
    store2.docs["resumes"].append({"id": "r1", "user_id": "ada"})
    result2 = apply_purge(privacy_plan, store=store2)
    assert result2["gdpr"]["deletedDocs"] == 1

    from app.storage.retention import apply_retention

    dry = apply_retention(None, plan)
    assert dry["dryRun"] is True
    assert dry["deleted"] >= 1
    skipped = apply_retention(None, {**plan, "enabled": False})
    assert skipped["skipped"] is True
    applied = apply_retention(store2, {**plan, "enabled": True, "matchIds": ["ghost"]})
    assert applied["skipped"] is False


def test_ci_workflow_runs_emulator_tests_and_fails_on_coverage_drop():
    text = Path(__file__).resolve().parents[2].joinpath(".github", "workflows", "ci.yml").read_text()
    assert "storage-emulator" in text
    assert "azurite" in text
    assert "--cov=app/storage" in text
    assert "--cov-fail-under=80" in text
    assert "--cov-fail-under=40" in text
    assert "junitxml" in text
    assert "playwright" in text
    assert "tests/test_storage_*.py" in text

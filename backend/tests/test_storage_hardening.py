"""Database PRD ops plane: capacity, lint, geo, PII, backfill, archive, chaos, load."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.metrics import reset as reset_metrics
from app.storage.analytics import export_analytics, warehouse_contract
from app.storage.archive import ARCHIVE_CONTAINER, archive_stale, restore_from_jsonl
from app.storage.backfill import RuBudgetExceeded, run_backfill
from app.storage.capacity import bicep_autoscale_snippet, capacity_plan, daily_ru_dashboard
from app.storage.catalog import render_cosmos_schema
from app.storage.chaos import reset as reset_chaos, throttle, region_outage
from app.storage.consistency import consistency_plan, container_consistency
from app.storage.cosmos import cosmos_client_kwargs
from app.storage.dal import CosmosDAL, with_retry
from app.storage.index_tuner import tune_all, tune_container
from app.storage.key_rotation import rotate_cosmos_key
from app.storage.loadtest import run_load
from app.storage.pii import decrypt_fields, encrypt_fields, mask_value, redact
from app.storage.query_lint import CrossPartitionScanError, lint_query, reset_profiles, top_queries
from app.storage.replication import failover_drill, replication_plan
from app.storage.sdk_policy import PINNED, canary, pinned_version
from app.storage.testing import FakeDatabase

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _reset_chaos_between_tests():
    reset_chaos()
    yield
    reset_chaos()


def test_autoscale_capacity_plan_and_daily_budget():
    serverless = capacity_plan(Settings(cosmos_throughput_mode="serverless"))
    assert serverless["mode"] == "serverless"
    assert serverless["iac"] == "infra/cosmos-autoscale.bicep"
    assert all(row["maxRu"] is None for row in serverless["containers"])
    auto = capacity_plan(Settings(cosmos_throughput_mode="autoscale", cosmos_autoscale_max_ru=4000))
    matches = next(row for row in auto["containers"] if row["id"] == "matches")
    logs = next(row for row in auto["containers"] if row["id"] == "event_log")
    assert matches["maxRu"] == 4000
    assert logs["maxRu"] == 1000
    dash = daily_ru_dashboard(ru_today=250_000, settings=Settings(cosmos_daily_ru_budget=250_000))
    assert dash["firing"] is True
    bicep = (REPO / "infra" / "cosmos-autoscale.bicep").read_text()
    assert "autoscaleSettings" in bicep
    assert "maxThroughput" in bicep
    assert "enableMultipleWriteLocations" in bicep_autoscale_snippet()


def test_query_lint_blocks_cross_partition_and_profiles_hot_queries():
    reset_profiles()
    blocked = lint_query("matches", "SELECT * FROM c")
    assert blocked.ok is False
    dal = CosmosDAL(FakeDatabase())
    dal.upsert("matches", {"id": "m1", "user_id": "u1", "status": "PENDING"})
    with pytest.raises(CrossPartitionScanError):
        dal.query("matches", "SELECT * FROM c")
    page = dal.query("matches", "SELECT * FROM c", partition_key="u1")
    assert page.items[0]["id"] == "m1"
    allowed = dal.query("job_sources", "SELECT * FROM c")
    assert allowed.items == []
    top = top_queries(1)
    assert top[0]["container"] in {"matches", "job_sources"}


def test_composite_index_tuner_reports_before_after_ru():
    report = tune_container("matches")
    assert report["existing"]
    all_reports = tune_all()
    assert all_reports["schema"] == "ajas.cosmos.index.tuner.v1"
    assert all_reports["reports"]


def test_cross_partition_pagination_is_stable():
    dal = CosmosDAL(FakeDatabase())
    for user, match_id in (("u1", "a"), ("u2", "b"), ("u1", "c"), ("u2", "d")):
        dal.upsert("matches", {"id": match_id, "user_id": user, "status": "PENDING"})
    seen: list[str] = []
    token = None
    while True:
        page = dal.query("matches", "SELECT * FROM c", max_items=1, continuation=token, allow_cross_partition=True)
        seen.extend(item["id"] for item in page.items)
        token = page.continuation
        if not token:
            break
    assert seen == ["a", "b", "c", "d"] or set(seen) == {"a", "b", "c", "d"}
    assert len(seen) == 4


def test_geo_replication_failover_drill():
    plan = replication_plan(Settings(cosmos_preferred_regions="eastus,westus"))
    assert plan["regions"] == ["eastus", "westus"]
    assert plan["rtoSeconds"] == 60
    passed = failover_drill(from_region="eastus", to_region="westus", elapsed_seconds=12)
    assert passed["passed"] is True
    failed = failover_drill(from_region="eastus", to_region="westus", elapsed_seconds=90)
    assert failed["passed"] is False


def test_pii_encrypt_mask_and_dal_redaction():
    assert mask_value("ada@ajas.dev") == "a***@ajas.dev"
    sealed = encrypt_fields("email_connections", {"access_token_enc": "tok-secret"}, secret="k")
    assert str(sealed["access_token_enc"]).startswith("enc.")
    opened = decrypt_fields("email_connections", sealed, secret="k")
    assert opened["access_token_enc"] == "tok-secret"
    redacted = redact("users", {"id": "u1", "email": "ada@ajas.dev", "password": "nope"})
    assert redacted["email"] == "a***@ajas.dev"
    assert "password" not in redacted
    dal = CosmosDAL(FakeDatabase())
    dal.upsert("users", {"id": "u1", "email": "ada@ajas.dev"})
    shown = dal.read("users", "u1", partition_key="u1", redact=True)
    assert shown["email"] == "a***@ajas.dev"


def test_cosmos_key_rotation_hot_reloads():
    first = rotate_cosmos_key("key-one")
    second = rotate_cosmos_key("key-two", previous="key-one")
    assert first["hotReload"] is True
    assert second["reminder"] == "quarterly"
    assert "docs/cosmos-ops.md" in second["runbook"]
    assert first["fingerprint"] != second["fingerprint"]


def test_backfill_v2_chunks_and_ru_guard():
    dal = CosmosDAL(FakeDatabase())
    for index in range(5):
        dal.upsert("matches", {"id": f"m{index}", "user_id": "u1", "status": "PENDING"})

    def add_flag(row):
        row["migrated"] = True
        return row

    result = run_backfill(dal, "matches", add_flag, chunk_size=2, ru_budget=10_000, partition_key="u1")
    assert result["updated"] == 5
    assert result["schema"] == "ajas.cosmos.backfill.v2"
    with pytest.raises(RuBudgetExceeded):
        run_backfill(dal, "matches", add_flag, chunk_size=1, ru_budget=0.5, partition_key="u1")


def test_analytics_export_scrubs_pii(tmp_path):
    dal = CosmosDAL(FakeDatabase())
    dal.upsert("matches", {"id": "m1", "user_id": "u1", "job_title": "Eng", "email": "hidden@ajas.dev"})
    counts = export_analytics(dal, tmp_path / "out", containers=("matches",))
    assert counts["matches"] == 1
    text = (tmp_path / "out" / "matches.jsonl").read_text()
    assert "hidden@ajas.dev" not in text
    assert warehouse_contract()["pii"] == "masked-or-redacted"


def test_cold_archive_and_restore(tmp_path):
    dal = CosmosDAL(FakeDatabase())
    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    dal.upsert("event_log", {"id": "e1", "user_id": "u1", "event_type": "X", "occurred_at": old, "created_at": old})
    blobs: dict[tuple[str, str], bytes] = {}

    def put(container, key, data):
        blobs[(container, key)] = data

    result = archive_stale(dal, container="event_log", days=365, put=put)
    assert result["moved"] == 1
    assert ARCHIVE_CONTAINER in {item[0] for item in blobs}
    with pytest.raises(KeyError):
        dal.read("event_log", "e1", partition_key="u1")
    path = tmp_path / "e1.jsonl"
    path.write_bytes(next(iter(blobs.values())))
    assert restore_from_jsonl(dal, path, container="event_log") == 1
    assert dal.read("event_log", "e1", partition_key="u1")["id"] == "e1"


def test_sdk_pin_and_canary():
    row = canary()
    assert PINNED == "4.17.1"
    assert pinned_version() == PINNED
    assert row["ok"] is True
    assert "requirements.txt" in row["rollback"]
    assert f"azure-cosmos=={PINNED}" in (REPO / "backend" / "requirements.txt").read_text()


def test_chaos_throttling_and_region_outage_retry():
    reset_chaos()
    reset_metrics()
    hits = {"n": 0}

    def _ok():
        hits["n"] += 1
        return {"ok": True}

    throttle(2)
    assert with_retry(_ok, retries=4, delay=0) == {"ok": True}
    assert hits["n"] == 1
    hits["n"] = 0
    region_outage(1)
    assert with_retry(_ok, retries=4, delay=0) == {"ok": True}
    reset_chaos()


def test_catalog_maps_api_owner_consistency_and_docs():
    rendered = render_cosmos_schema()
    committed = (REPO / "docs" / "cosmos.schema.md").read_text()
    assert committed == rendered
    assert "Consistency" in committed
    assert "GET /api/v1/matches" in committed
    assert container_consistency("user_settings") == "Strong"
    assert container_consistency("matches") == "Session"
    strong = consistency_plan(Settings(cosmos_consistency="Strong"))
    assert strong["containers"]["matches"] == "Strong"
    assert "docs/cosmos-ops.md" in (REPO / "docs" / "db-setup.md").read_text()
    kwargs = cosmos_client_kwargs(Settings(cosmos_preferred_regions="eastus,westus", cosmos_consistency="Session"))
    assert kwargs["preferred_locations"] == ["eastus", "westus"]
    assert kwargs["consistency_level"] == "Session"


def test_ru_budget_load_stays_under_slo():
    result = run_load(iterations=20, ru_budget=50_000)
    assert result["ok"] is True
    assert result["ruPerOp"] <= 5
    assert set(result["paths"]) >= {"users.point", "matches.list"}

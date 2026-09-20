"""Database plane: schema docs, typed DAL, DLQ, seeds, contracts, retention job."""

from __future__ import annotations

from pathlib import Path

import azure.functions as func

from app.dlq import depth, reset as reset_dlq
from app.queue_health import snapshot as queue_snapshot
from app.slo_pipelines import reset as reset_slo
from app.storage.blob_layout import checksum_blob_name, config_blob_containers
from app.storage.catalog import render_cosmos_schema
from app.storage.contracts import ENDPOINTS, endpoint_table
from app.storage.dal import CosmosDAL
from app.storage.dispatch import handle_queue_payload
from app.storage.entities import StoredResume, User
from app.storage.entity_dal import core_repositories
from app.storage.jobs import run_retention_job
from app.storage.provision import provision_all
from app.storage.queue_schemas import QUEUE_SCHEMAS, config_queue_names
from app.storage.seeds import seed_blobs, seed_documents
from app.storage.testing import FakeDatabase, MemoryDocumentStore

REPO = Path(__file__).resolve().parents[2]


def test_committed_cosmos_schema_matches_catalog():
    rendered = render_cosmos_schema()
    committed = (REPO / "docs" / "cosmos.schema.md").read_text()
    assert committed == rendered
    assert "| `matches` |" in committed
    assert "`/user_id`" in committed


def test_provision_includes_config_queues_and_prd_blobs():
    plan = provision_all(dry_run=True)
    for name in config_queue_names():
        assert name in plan["queues"]
        assert f"{name}-poison" in plan["queues"]
    for name in ("review-artifacts", "resumes", "job-raw", "mail-attachments"):
        assert name in plan["blobs"]
    assert set(config_blob_containers()) <= set(plan["blobs"])
    assert set(config_queue_names()) <= set(QUEUE_SCHEMAS)


def test_typed_entity_dal_crud_and_pagination():
    repos = core_repositories(CosmosDAL(FakeDatabase()))
    repos["users"].upsert(User(id="u1", email="a@ajas.dev", display_name="Ada", created_at="t", updated_at="t"))
    assert repos["users"].get("u1", partition_key="u1").email == "a@ajas.dev"
    repos["resumes"].upsert(
        StoredResume(
            id="r1",
            user_id="u1",
            original_filename="cv.pdf",
            mime_type="application/pdf",
            file_size=12,
            blob_uri="u1/r1/cv.pdf",
            checksum_sha256="ab",
            created_at="t",
            updated_at="t",
        )
    )
    page = repos["resumes"].list_partition("u1", max_items=10)
    assert page.items[0]["id"] == "r1"
    repos["resumes"].delete("r1", partition_key="u1")


def test_queue_dispatch_validates_backpressure_and_dlq():
    reset_dlq()
    reset_slo()
    stamp = "2026-01-15T12:00:00+00:00"
    ok = handle_queue_payload(
        "resume-parse",
        {
            "enqueued_at": stamp,
            "user_id": "u1",
            "resume_id": "r1",
            "blob_path": "u1/r1/cv.pdf",
            "mime_type": "application/pdf",
        },
        depth=0,
    )
    assert ok["status"] == "ok"
    shed = handle_queue_payload("resume-parse", {"enqueued_at": stamp}, depth=500)
    assert shed["status"] == "shed"
    dead = handle_queue_payload("resume-parse", {"enqueued_at": stamp}, depth=0)
    assert dead["status"] == "dead-letter"
    poison = handle_queue_payload(
        "resume-parse",
        {
            "enqueued_at": stamp,
            "user_id": "u1",
            "resume_id": "r1",
            "blob_path": "u1/r1/cv.pdf",
            "mime_type": "application/pdf",
        },
        dequeue_count=9,
    )
    assert poison["status"] == "poison"
    assert depth() >= 1
    health = queue_snapshot(depths={"crawl-runs": 120, "crawl-runs-poison": 2}, dlq_depth=depth())
    assert health["alerts"]


def test_blob_checksum_names_and_seed_uploads():
    assert checksum_blob_name("cv.pdf", "abcdef1234567890") == "cv.abcdef123456.pdf"
    uploaded: dict[tuple[str, str], bytes] = {}

    def put(container: str, key: str, data: bytes) -> None:
        uploaded[(container, key)] = data

    paths = seed_blobs(put)
    assert ("resumes", paths["resumes"]) in uploaded
    assert uploaded[("job-raw", paths["job-raw"])].startswith(b"{")


def test_endpoint_contract_paths_exist_in_backend():
    import json

    root = REPO / "backend" / "app" / "features"
    sources = "\n".join(path.read_text() for path in root.glob("*.py"))
    dumped = json.loads((REPO / "contracts" / "endpoints.json").read_text())
    assert dumped == endpoint_table()
    for row in ENDPOINTS:
        if row["id"] == "health":
            assert 'route="health"' in sources
            continue
        path = row["path"]
        assert any(token in sources for token in (path, path.replace("/api/", ""), path.split("{")[0]))


def test_retention_timer_is_registered(function_names):
    assert "retention_purge" in function_names
    assert "ops_queues" in function_names
    assert "ops_retention" in function_names


def test_retention_job_and_ops_queue_endpoint():
    import json

    from app.features.ops import ops_queues, ops_retention

    store = MemoryDocumentStore()
    out = run_retention_job(store, jobs=[], emails=[], matches=[])
    assert out["schema"] == "ajas.retention.job.v1"
    assert "blobLifecycle" in out
    headers = {"Authorization": "Bearer local-user", "X-Role": "admin"}
    body = json.loads(
        ops_queues(func.HttpRequest(method="GET", url="http://localhost/api/v1/ops/queues", headers=headers, params={}, body=b"")).get_body()
    )
    assert "queues" in body and "pipelines" in body
    posted = json.loads(
        ops_retention(
            func.HttpRequest(method="POST", url="http://localhost/api/v1/ops/retention", headers=headers, params={}, body=b"{}")
        ).get_body()
    )
    assert "result" in posted


def test_env_sample_and_compose_and_coverage_gate():
    env = (REPO / ".env.sample").read_text()
    assert "COSMOS_CONNECTION_STRING" in env
    assert "KEY_VAULT_URI" in env
    compose = (REPO / "docker-compose.yml").read_text()
    assert "azurite" in compose
    assert "cosmosdb/linux/azure-cosmos-emulator" in compose
    ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
    assert "junitxml" in ci
    assert "--cov-fail-under=80" in ci
    assert "--cov-fail-under=40" in ci
    assert seed_documents()["users"]

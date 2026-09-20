"""Azurite-backed blob/queue tests plus fake-Cosmos integration coverage."""

from __future__ import annotations

import json
import os

import pytest

from app.storage.blob_layout import job_raw_key, resume_key
from app.storage.dal import CosmosDAL
from app.storage.provision import provision_blobs, provision_queues
from app.storage.queue_schemas import ResumeParseMessage, encode_queue_message, parse_queue_message
from app.storage.seeds import apply_seed, seed_documents
from app.storage.testing import FakeDatabase

CONN = "UseDevelopmentStorage=true"


def _azurite_blob():
    try:
        from azure.storage.blob import BlobServiceClient

        client = BlobServiceClient.from_connection_string(CONN)
        client.get_service_properties()
        return client
    except Exception as exc:  # pragma: no cover - skipped when emulator is down
        pytest.skip(f"Azurite blob not available: {exc}")


def _azurite_queue():
    try:
        from azure.storage.queue import QueueServiceClient

        client = QueueServiceClient.from_connection_string(CONN)
        client.get_service_properties()
        return client
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"Azurite queue not available: {exc}")


@pytest.mark.emulator
def test_azurite_blob_roundtrip_uses_layout_keys():
    service = _azurite_blob()
    provision_blobs(service)
    key = resume_key("seed-user-001", "seed-resume-001", "ada-lovelace.pdf")
    container = service.get_container_client("resumes")
    container.upload_blob(name=key, data=b"%PDF-seed", overwrite=True, metadata={"user_id": "seed-user-001"})
    downloaded = container.download_blob(key).readall()
    assert downloaded == b"%PDF-seed"
    raw_key = job_raw_key("ten-1", "post-9", "2026-01-15T12:00:00+00:00")
    raw = service.get_container_client("job-raw")
    raw.upload_blob(name=raw_key, data=b'{"id":"post-9"}', overwrite=True)
    assert b"post-9" in raw.download_blob(raw_key).readall()


@pytest.mark.emulator
def test_azurite_queue_validates_schema_and_poison_queue():
    service = _azurite_queue()
    provision_queues(service)
    stamp = "2026-01-15T12:00:00+00:00"
    message = ResumeParseMessage(
        enqueued_at=stamp,
        user_id="seed-user-001",
        resume_id="seed-resume-001",
        blob_path="seed-user-001/seed-resume-001/ada-lovelace.pdf",
        mime_type="application/pdf",
    )
    client = service.get_queue_client("resume-parse")
    client.send_message(json.dumps(encode_queue_message(message)))
    found = client.receive_messages(max_messages=1)
    bodies = [json.loads(item.content) for item in found]
    assert bodies
    parsed = parse_queue_message("resume-parse", bodies[0])
    assert parsed.resume_id == "seed-resume-001"
    poison = service.get_queue_client("resume-parse-poison")
    poison.send_message(json.dumps({"invalid": True}))
    poison_items = list(poison.receive_messages(max_messages=1))
    assert poison_items


def test_cosmos_emulator_or_fake_seed_crud():
    """Live Cosmos when COSMOS_CONNECTION_STRING is set; otherwise FakeDatabase."""
    conn = os.environ.get("COSMOS_CONNECTION_STRING") or ""
    if conn:
        from azure.cosmos import CosmosClient

        from app.storage.catalog import ensure_all_containers

        client = CosmosClient.from_connection_string(conn)
        database = client.create_database_if_not_exists(id="ajas")
        ensure_all_containers(database)
        dal = CosmosDAL(database)
    else:
        dal = CosmosDAL(FakeDatabase())
    counts = apply_seed(dal)
    assert counts["users"] == 1
    user = dal.read("users", "seed-user-001", partition_key="seed-user-001")
    assert user["email"] == "ada@ajas.dev"
    page = dal.query("resumes", "SELECT * FROM c", partition_key="seed-user-001")
    assert page.items[0]["id"] == "seed-resume-001"
    docs = seed_documents()
    assert set(docs) >= {"users", "resumes", "auto_apply_attempts", "matches", "email_threads"}

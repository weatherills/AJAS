"""Provisioning script, blob layout, and queue schemas."""

from __future__ import annotations

import json
from pathlib import Path

from app.storage.blob_layout import (
    BLOB_CONTAINERS,
    auto_apply_key,
    blob_container_names,
    job_raw_key,
    lifecycle_rules,
    mail_attachment_key,
    metadata_for,
    resume_key,
    review_artifact_key,
)
from app.storage.provision import connection_info, cosmos_kwargs_preview, provision_all, provision_blobs, provision_cosmos, provision_queues
from app.storage.queue_schemas import (
    CrawlRunMessage,
    MatchComputeMessage,
    QueueSchemaError,
    ResumeParseMessage,
    all_queue_names,
    parse_queue_message,
    poison_queue_name,
    queue_names,
    should_dead_letter,
)
from app.storage.testing import FakeDatabase


class _BlobService:
    def __init__(self) -> None:
        self.created: list[str] = []

    def get_container_client(self, name: str):
        parent = self

        class _Client:
            def create_container(self_inner) -> None:
                parent.created.append(name)

            def exists(self_inner) -> bool:
                return name in parent.created

        return _Client()


class _QueueService:
    def __init__(self) -> None:
        self.created: list[str] = []

    def create_queue(self, name: str) -> None:
        if name in self.created:
            raise Exception("QueueAlreadyExists")
        self.created.append(name)

    def get_queue_client(self, name: str):
        parent = self

        class _Client:
            def exists(self_inner) -> bool:
                return name in parent.created

        return _Client()


def test_provision_dry_run_lists_cosmos_blobs_and_queues():
    plan = provision_all(dry_run=True)
    assert plan["status"] == "planned"
    assert "matches" in plan["cosmos"]
    assert "users" in plan["cosmos"]
    assert "resumes" in plan["blobs"]
    assert "job-raw" in plan["blobs"]
    assert "crawl-runs" in plan["queues"]
    assert "crawl-runs-poison" in plan["queues"]
    info = connection_info()
    assert info["COSMOS_DATABASE"] == "ajas"
    preview = cosmos_kwargs_preview()
    raw = next(row for row in preview if row["id"] == "job_postings_raw")
    assert raw["default_ttl"] == 90 * 86_400
    runs = next(row for row in preview if row["id"] == "match_runs")
    assert runs["unique_key_policy"]["uniqueKeys"][0]["paths"] == ["/idempotency_key"]


def test_provision_cosmos_blobs_queues_against_fakes():
    db = FakeDatabase()
    created = provision_cosmos(db)
    assert "matches" in created
    assert "event_log" in created
    assert any(item["id"] == "users" for item in db.created)
    blobs = provision_blobs(_BlobService())
    assert set(blobs) == set(blob_container_names())
    queues = provision_queues(_QueueService())
    assert "decision-events-poison" in queues
    assert set(queues) == set(all_queue_names())


def test_provision_script_dry_run_exits_zero(tmp_path, monkeypatch, capsys):
    import runpy

    script = Path("/workspace/backend/scripts/provision_storage.py")
    monkeypatch.setattr("sys.argv", ["provision_storage.py", "--dry-run", "--seed"])
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["seeded"]["users"] == 1
    assert payload["cosmosPreview"]


def test_blob_layout_keys_metadata_and_lifecycle():
    assert resume_key("u1", "r1", "cv.pdf") == "u1/r1/cv.pdf"
    assert job_raw_key("ten-1", "post-9", "2026-01-15T12:00:00+00:00").startswith("ten-1/post-9/")
    assert review_artifact_key("u1", "m1", "summary.md") == "u1/m1/summary.md"
    assert mail_attachment_key("acct", "msg", "att") == "acct/msg/att"
    assert auto_apply_key("u1", "a1", "screenshot", "page.png") == "u1/a1/screenshot/page.png"
    names = blob_container_names()
    assert names == tuple(item.name for item in BLOB_CONTAINERS)
    meta = metadata_for("resumes", user_id="u1", resume_id="r1", unused="x")
    assert meta == {"user_id": "u1", "resume_id": "r1"}
    rules = {rule["container"]: rule for rule in lifecycle_rules()}
    assert rules["job-raw"]["actions"]["delete"]["daysAfterModificationGreaterThan"] == 90
    assert rules["resumes"]["actions"]["delete"]["daysAfterModificationGreaterThan"] == 730
    assert "tierToCool" in rules["job-raw"]["actions"]


def test_queue_schemas_validate_and_dead_letter():
    stamp = "2026-01-15T12:00:00+00:00"
    crawl = parse_queue_message(
        "crawl-runs",
        {
            "enqueued_at": stamp,
            "source_tenant_id": "t1",
            "source_id": "greenhouse",
            "run_id": "run-1",
        },
    )
    assert isinstance(crawl, CrawlRunMessage)
    parsed = parse_queue_message(
        "resume-parse",
        {
            "enqueued_at": stamp,
            "user_id": "u1",
            "resume_id": "r1",
            "blob_path": "u1/r1/cv.pdf",
            "mime_type": "application/pdf",
        },
    )
    assert isinstance(parsed, ResumeParseMessage)
    match = parse_queue_message(
        "match-compute",
        {
            "enqueued_at": stamp,
            "user_id": "u1",
            "resume_id": "r1",
            "job_id": "j1",
            "idempotency_key": "u1:r1:j1:v1",
        },
    )
    assert isinstance(match, MatchComputeMessage)
    try:
        parse_queue_message("resume-parse", {"enqueued_at": stamp})
        assert False, "expected QueueSchemaError"
    except QueueSchemaError as exc:
        assert exc.dead_letter is True
    assert should_dead_letter(5) is True
    assert should_dead_letter(4) is False
    assert poison_queue_name("match-compute") == "match-compute-poison"
    assert set(queue_names()) >= {"crawl-runs", "resume-parse", "match-compute", "auto-apply-requests", "mail-ingest"}

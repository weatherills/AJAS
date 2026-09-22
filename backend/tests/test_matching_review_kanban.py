"""Matching, Review, and DB DAO Kanban: named APIs, indexes, TTL, audit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.matching.constants import (
    EVIDENCE_TTL_SECONDS,
    RECORDS_INDEXING,
    SCORING_RUNS_CONTAINER,
    SCORING_RUNS_PK,
    SCHEMA_VERSION,
)
from app.matching.containers import container_specs as matching_specs
from app.matching.keys import utc_now
from app.matching.records import match_record_id
from app.review.constants import MATCHES_INDEXING, QUEUE_TTL_SECONDS
from app.review.containers import container_specs as review_specs
from app.storage.catalog import container_by_id, ttl_containers
from app.storage.dao import MatchingDAO, ReviewDAO, domain_daos, ensure_mvp_containers
from app.storage.dal import CosmosDAL
from app.storage.epic import resolve_container
from app.storage.testing import FakeDatabase

USER = "kanban-user"


def _daos():
    db = FakeDatabase()
    ensure_mvp_containers(db)
    return domain_daos(CosmosDAL(db)), db


def test_ensure_matching_containers_include_scoring_runs_and_indexes():
    daos, db = _daos()
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    created = matching.ensure_matching_containers(FakeDatabase())
    assert "match_records" in created
    assert "match_evidence" in created
    assert "scoring_runs" in created
    specs = {item["id"]: item for item in matching_specs()}
    assert specs["match_records"]["partition_key"] == "/userId"
    assert specs["match_evidence"]["partition_key"] == "/userId"
    assert specs[SCORING_RUNS_CONTAINER]["partition_key"] == SCORING_RUNS_PK == "/userId"
    record_paths = [[part["path"] for part in index] for index in RECORDS_INDEXING["compositeIndexes"]]
    assert ["/userId", "/jobId"] in record_paths
    assert ["/userId", "/createdAt"] in record_paths
    evidence = container_by_id("match_evidence")
    ev_paths = [[part["path"] for part in index] for index in evidence.indexing_policy["compositeIndexes"]]
    assert ["/userId", "/matchId", "/createdAt"] in ev_paths
    assert evidence.default_ttl == EVIDENCE_TTL_SECONDS
    assert container_by_id("scoring_runs").unique_keys == (("/correlationId",),)
    assert resolve_container("scoring_runs") == "scoring_runs"
    assert db is not None


def test_deterministic_create_match_record_and_schema_version():
    daos, _ = _daos()
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    first = matching.create_match_record(USER, job_id="job-a", resume_id="res-a", score=80, model_version="matching-v1")
    expected = match_record_id(user_id=USER, job_id="job-a", resume_id="res-a", model_version="matching-v1")
    assert first["record"]["id"] == expected
    assert first["record"]["schemaVersion"] == SCHEMA_VERSION
    assert first["status"] == "created"
    second = matching.create_match_record(USER, job_id="job-a", resume_id="res-a", score=81, model_version="matching-v1")
    assert second["record"]["id"] == expected
    v2 = matching.create_match_record(USER, job_id="job-a", resume_id="res-a", score=82, model_version="matching-v2")
    assert v2["record"]["id"] != expected
    assert v2["record"]["modelVersion"] == "matching-v2"


def test_get_match_with_evidence_is_user_scoped_and_redacts_snippets():
    daos, _ = _daos()
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    created = matching.create_match_record(
        USER, job_id="job-e", resume_id="res-e", score=90, evidence=["secret@acme.test is a skill"]
    )
    match_id = created["record"]["id"]
    matching.upsert_evidence_batch(
        USER,
        match_id,
        [{"type": "skill", "weight": 0.8, "orderIndex": 0, "text": "ada@ajas.dev kubernetes"}],
        ttl_seconds=180 * 86_400,
    )
    bundle = matching.get_match_with_evidence(USER, match_id)
    assert bundle["record"]["id"] == match_id
    assert bundle["evidence"]
    for row in bundle["evidence"]:
        assert "ada@ajas.dev" not in str(row)
        assert "text" not in row or "***" in str(row.get("text"))
        assert "snippetHash" in row or "sentences" in row
    try:
        matching.get_match_with_evidence("other-user", match_id)
        raise AssertionError("expected miss")
    except Exception:
        pass


def test_list_matches_filters_pagination_and_created_at_desc():
    daos, _ = _daos()
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    matching.create_match_record(USER, job_id="j1", resume_id="r1", score=60)
    matching.create_match_record(USER, job_id="j1", resume_id="r2", score=90)
    matching.create_match_record(USER, job_id="j2", resume_id="r1", score=75)
    page = matching.list_matches(USER, job_id="j1", min_score=70, limit=10)
    assert all(row["jobId"] == "j1" for row in page["items"])
    assert all(float(row["score"]) >= 70 for row in page["items"])
    stamps = [row.get("createdAt") or "" for row in page["items"]]
    assert stamps == sorted(stamps, reverse=True)
    tiny = matching.list_matches(USER, limit=1)
    assert tiny["nextCursor"]
    page2 = matching.list_matches(USER, cursor=tiny["nextCursor"], limit=1)
    assert page2["items"]
    assert tiny["items"][0]["id"] != page2["items"][0]["id"]


def test_upsert_evidence_batch_hashes_raw_text_and_sets_ttl():
    daos, _ = _daos()
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    created = matching.create_match_record(USER, job_id="j", resume_id="r", score=70)
    batch = matching.upsert_evidence_batch(
        USER,
        created["record"]["id"],
        [
            {"type": "keyword", "weight": 1.2, "orderIndex": 0, "text": "raw secret phrase"},
            {"type": "skill", "weight": 0.5, "orderIndex": 1, "snippetHash": "abc"},
        ],
        ttl_seconds=123,
    )
    assert batch["count"] == 2
    assert batch["ttl"] == 123
    for item in batch["items"]:
        assert "raw secret phrase" not in str(item)
        assert item["ttl"] == 123
        assert item["snippetHash"]
        assert "text" not in item
        assert "sentences" not in item


def test_begin_end_scoring_run_and_observability():
    daos, _ = _daos()
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    begun = matching.begin_scoring_run(USER, job_id="j", resume_id="r", model_version="matching-v1")
    assert begun["status"] == "running"
    assert begun["correlationId"]
    assert begun["schemaVersion"] == SCHEMA_VERSION
    ended = matching.end_scoring_run(USER, begun["correlationId"], status="completed", latency_ms=12)
    assert ended["status"] == "completed"
    assert ended["latencyMs"] == 12
    assert ended["errorCode"] is None
    metrics = matching.scoring_metrics()
    events = {row["event"] for row in metrics}
    assert "scoring_begin" in events
    assert "scoring_end" in events
    assert any(row.get("correlationId") == begun["correlationId"] for row in metrics)


def test_retention_ttl_and_prune_latest_n():
    daos, _ = _daos()
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    for score in range(8):
        matching.create_match_record(USER, job_id="keep", resume_id="cv", score=float(score))
    pruned = matching.prune_retention(USER, keep=3)
    assert pruned["keep"] == 3
    assert pruned["deleted"] >= 1
    ttl = {spec.id: spec.default_ttl for spec in ttl_containers()}
    assert ttl["match_evidence"] == 180 * 86_400


def test_backfill_rescore_on_new_model_version_is_idempotent():
    daos, _ = _daos()
    matching: MatchingDAO = daos["matching"]  # type: ignore[assignment]
    matching.create_match_record(USER, job_id="j", resume_id="r", score=50, model_version="matching-v1")
    pairs = [{"jobId": "j", "resumeId": "r", "score": 88, "modelVersion": "matching-v9"}]
    first = matching.backfill_rescore(USER, pairs, model_version="matching-v9")
    second = matching.backfill_rescore(USER, pairs, model_version="matching-v9")
    assert first["count"] == second["count"] == 1
    assert first["items"][0]["id"] == second["items"][0]["id"]
    assert first["items"][0]["modelVersion"] == "matching-v9"


def test_ensure_review_containers_and_index_policies():
    daos, _ = _daos()
    review: ReviewDAO = daos["review"]  # type: ignore[assignment]
    created = review.ensure_review_containers(FakeDatabase())
    assert set(created) >= {"matches", "decision_events"}
    assert resolve_container("review_queue") == "matches"
    assert resolve_container("review_decisions") == "decision_events"
    specs = {item["id"]: item for item in review_specs()}
    assert specs["matches"]["partition_key"] == "/user_id"
    paths = [[part["path"] for part in index] for index in MATCHES_INDEXING["compositeIndexes"]]
    assert ["/user_id", "/status", "/queued_at"] in paths
    assert ["/user_id", "/job_id"] in paths
    assert ["/user_id", "/created_at"] in paths
    decisions = container_by_id("decision_events")
    dpaths = [[part["path"] for part in index] for index in decisions.indexing_policy["compositeIndexes"]]
    assert ["/user_id", "/job_id"] in dpaths


def test_enqueue_review_item_dedupes_and_sets_expiry():
    daos, _ = _daos()
    review: ReviewDAO = daos["review"]  # type: ignore[assignment]
    first = review.enqueue_review_item(USER, job_id="jq", resume_id="rq", job_title="Staff", ai_score=0.9)
    second = review.enqueue_review_item(USER, job_id="jq", resume_id="rq")
    assert first["status"] == "created"
    assert second["status"] == "existing"
    assert first["item"]["id"] == second["item"]["id"]
    assert first["item"]["expiresAt"]
    assert first["item"]["ttl"] == QUEUE_TTL_SECONDS
    assert first["item"]["userId"] == USER


def test_list_queue_status_and_cursor_sort():
    daos, _ = _daos()
    review: ReviewDAO = daos["review"]  # type: ignore[assignment]
    review.enqueue_review_item(USER, job_id="a", resume_id="r")
    review.enqueue_review_item(USER, job_id="b", resume_id="r")
    pending = review.list_queue(USER, "PENDING", limit=25)
    assert {row["job_id"] for row in pending["items"]} == {"a", "b"}
    stamps = [row["queued_at"] for row in pending["items"]]
    assert stamps == sorted(stamps, reverse=True)
    decided = review.save_decision(USER, job_id="a", resume_id="r", decision="approve", reason="strong fit")
    remaining = review.list_queue(USER, "PENDING")
    assert all(row["job_id"] != "a" for row in remaining["items"])
    assert decided["decision"]["reason"] == "strong fit"


def test_save_decision_etag_audit_and_feedback():
    daos, _ = _daos()
    review: ReviewDAO = daos["review"]  # type: ignore[assignment]
    queued = review.enqueue_review_item(USER, job_id="jd", resume_id="rd", ai_score=0.8)
    saved = review.save_decision(
        USER,
        queued["item"]["id"],
        "reject",
        reason="location",
        etag=queued["item"]["_etag"],
    )
    assert saved["match"]["status"] == "REJECTED"
    assert saved["audit"]["event_type"] == "DECISION_RECORDED"
    assert "location" not in str(saved["audit"]["payload"])
    assert saved["feedback"]["decision"] == "reject"
    assert saved["feedback"]["match_id"] == queued["item"]["id"]


def test_queue_ttl_expiry_worker_marks_stale_pending():
    daos, _ = _daos()
    review: ReviewDAO = daos["review"]  # type: ignore[assignment]
    queued = review.enqueue_review_item(USER, job_id="old", resume_id="r", ttl_seconds=1)
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    row = queued["item"]
    row["expiresAt"] = past
    review.repo("matches").upsert(row, etag=row["_etag"])
    result = review.expire_queue(USER, now=utc_now())
    assert queued["item"]["id"] in result["expired"]
    listed = review.list_queue(USER, "PENDING")
    assert queued["item"]["id"] not in {item["id"] for item in listed["items"]}


def test_db_ttl_indexes_daos_pagination_and_smoke():
    daos, _ = _daos()
    ttl = {spec.id: spec.default_ttl for spec in ttl_containers()}
    assert ttl["match_evidence"] == 180 * 86_400
    assert ttl["job_postings_raw"] == 90 * 86_400
    assert container_by_id("matches").default_ttl is None
    apply_dao = daos["auto_apply"]
    resumes = daos["resumes"]
    ingest = daos["job_ingest"]
    email = daos["email"]
    privacy = daos["privacy"]
    run = apply_dao.create_apply_run(USER, job_id="j", resume_id="r")  # type: ignore[union-attr]
    again = apply_dao.create_apply_run(USER, job_id="j", resume_id="r")  # type: ignore[union-attr]
    assert run["item"]["id"] == again["item"]["id"]
    resume = resumes.create_resume(USER, original_filename="cv.pdf")  # type: ignore[union-attr]
    resumes.attach_file(USER, resume["id"])  # type: ignore[union-attr]
    posting = ingest.upsert_posting(canonical_key="role|city|co", title="Eng", source="greenhouse")  # type: ignore[union-attr]
    assert posting["item"]["id"]
    thread = email.upsert_thread("acct", USER, subject="Hi")  # type: ignore[union-attr]
    email.upsert_message("acct", thread["id"], from_address="a@b.test", body_text="hi")  # type: ignore[union-attr]
    req = privacy.create_export_request(USER)  # type: ignore[union-attr]
    assert req["kind"] == "export"
    listed = apply_dao.list_runs(USER, limit=10)  # type: ignore[union-attr]
    assert "nextCursor" in listed
    assert "auto_apply" in daos and "matching" in daos and "review" in daos

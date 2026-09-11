"""Review & Decision Backend PRD — HTTP API, auth, queues."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import review_decision as routes
from app.review.blobs import InMemoryBlobStore, sas_is_expired
from app.review.constants import MAX_COMMENT_CHARS
from app.review.memory import InMemoryReviewStore
from app.review.queues import InMemoryJobQueue
from app.review.runtime import set_service
from app.review.service import ReviewService

USER = "user-1"
OTHER = "user-2"


class Clock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime.now(timezone.utc)

    def __call__(self) -> str:
        return self.now.isoformat().replace("+00:00", "Z")

    def advance(self, **kwargs) -> None:
        self.now = self.now + timedelta(**kwargs)


@pytest.fixture
def store():
    return InMemoryReviewStore()


@pytest.fixture
def queue():
    return InMemoryJobQueue()


@pytest.fixture
def blobs():
    return InMemoryBlobStore()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def svc(monkeypatch, store, queue, blobs, clock):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = ReviewService(store=store, queue=queue, blobs=blobs, clock=clock)
    set_service(service)
    yield service
    set_service(None)
    get_settings.cache_clear()


def _req(
    method: str,
    url: str,
    *,
    user: str | None = USER,
    json_body=None,
    params: dict | None = None,
    route: dict | None = None,
    headers: dict | None = None,
    scopes: str | None = None,
) -> func.HttpRequest:
    hdrs = dict(headers or {})
    body = b""
    if user:
        hdrs["Authorization"] = f"Bearer {user}"
    if scopes is not None:
        hdrs["X-Scopes"] = scopes
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


def _seed(store: InMemoryReviewStore, user_id=USER, **overrides):
    payload = dict(
        job_id="job-1",
        resume_id="resume-1",
        job_title="Staff Platform Engineer",
        company="Acme",
        location="Remote",
        ai_score=88.0,
        suggestion="approve",
        why="Strong overlap on platform work.",
        summary="Good match for staff-level platform roles.",
        highlights_json=["Python", "Kubernetes"],
    )
    payload.update(overrides)
    return store.create_match(user_id, **payload)


def test_function_app_registers_review_routes(function_names):
    assert "list_matches" in function_names
    assert "get_match" in function_names
    assert "create_decision" in function_names
    assert "reopen_match" in function_names
    assert "list_saved_jobs" in function_names
    assert "decision_history" in function_names
    assert "list_decisions" in function_names
    assert "decision_events_job" in function_names
    assert "review_enrich_job" in function_names
    assert "health" in function_names


def test_unauthenticated_is_401(svc):
    resp = routes.list_matches(_req("GET", "http://localhost/api/v1/matches", user=None))
    assert resp.status_code == 401
    assert _body(resp)["error"]["code"] == "UNAUTHENTICATED"


def test_missing_write_scope_is_403(svc, store):
    match = _seed(store)
    resp = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "k1", "If-Match": match.etag},
            scopes="read:review",
        )
    )
    assert resp.status_code == 403
    assert _body(resp)["error"]["code"] == "FORBIDDEN"


def test_list_pending_is_user_scoped_with_filters_and_pagination(svc, store):
    _seed(store, job_id="j1", job_title="Staff Engineer", ai_score=88)
    _seed(store, job_id="j2", job_title="Data Analyst", company="Globex", ai_score=40, suggestion="reject")
    _seed(store, user_id=OTHER, job_id="j1", job_title="Other User Role", ai_score=99)
    resp = routes.list_matches(
        _req(
            "GET",
            "http://localhost/api/v1/matches",
            params={"status": "pending", "minScore": "80", "jobTitle": "staff"},
        )
    )
    assert resp.status_code == 200
    items = _body(resp)["items"]
    assert {item["jobId"] for item in items} == {"j1"}
    assert items[0]["status"] == "pending"
    assert items[0]["score"] == 88.0
    extra = [_seed(store, job_id=f"extra-{i}", job_title=f"Role {i}", ai_score=90) for i in range(12)]
    paged = routes.list_matches(
        _req("GET", "http://localhost/api/v1/matches", params={"status": "pending", "pageSize": "10"})
    )
    body = _body(paged)
    assert len(body["items"]) == 10
    assert "continuationToken" in body
    page2 = routes.list_matches(
        _req(
            "GET",
            "http://localhost/api/v1/matches",
            params={"status": "pending", "pageSize": "10", "continuation": body["continuationToken"]},
        )
    )
    ids = {item["matchId"] for item in body["items"]} | {item["matchId"] for item in _body(page2)["items"]}
    assert extra[0].id in ids
    other = routes.list_matches(
        _req("GET", "http://localhost/api/v1/matches", user=OTHER, params={"status": "pending"})
    )
    assert {item["jobId"] for item in _body(other)["items"]} == {"j1"}


def test_detail_is_404_for_other_user(svc, store):
    match = _seed(store)
    missing = routes.get_match(
        _req(
            "GET",
            f"http://localhost/api/v1/matches/{match.id}",
            user=OTHER,
            route={"matchId": match.id},
        )
    )
    assert missing.status_code == 404
    ok = routes.get_match(_req("GET", f"http://localhost/api/v1/matches/{match.id}", route={"matchId": match.id}))
    assert ok.status_code == 200
    body = _body(ok)
    assert body["match"]["summary"].startswith("Good match")
    assert body["match"]["score"] == 88.0
    assert body["match"]["why"]
    assert body["match"]["suggestion"] == "approve"
    assert "se=" in body["blobs"]["jobUrl"]
    assert "se=" in body["blobs"]["resumeUrl"]
    assert "sig=" in body["blobs"]["jobUrl"]
    assert not sas_is_expired(body["blobs"]["jobUrl"])
    assert sas_is_expired(body["blobs"]["jobUrl"], now=datetime.now(timezone.utc) + timedelta(minutes=11))


def test_missing_rationale_serves_cache_and_enqueues_enrich(svc, store, queue):
    match = _seed(store, job_id="sparse", summary=None, why=None, highlights_json=None, suggestion="none")
    resp = routes.get_match(_req("GET", f"http://localhost/api/v1/matches/{match.id}", route={"matchId": match.id}))
    assert resp.status_code == 200
    body = _body(resp)
    assert body["match"]["summary"] is None
    assert queue.of("review-enrich")
    assert queue.of("review-enrich")[0]["eventType"] == "EnrichRequested"
    audits = store.list_audit(USER, match_id=match.id, event_type="DEGRADED_VIEW")
    assert len(audits) == 1


def test_decision_requires_idempotency_and_if_match(svc, store):
    match = _seed(store)
    missing_key = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve"},
            route={"matchId": match.id},
            headers={"If-Match": match.etag},
        )
    )
    assert missing_key.status_code == 400
    missing_etag = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "k1"},
        )
    )
    assert missing_etag.status_code == 400


def test_stale_etag_is_412(svc, store):
    match = _seed(store)
    resp = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "k1", "If-Match": "999"},
        )
    )
    assert resp.status_code == 412
    assert _body(resp)["error"]["code"] == "PRECONDITION_FAILED"


def test_decide_is_idempotent_and_enqueues_without_comment(svc, store, queue):
    match = _seed(store)
    first = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve", "comment": "Ship it"},
            route={"matchId": match.id},
            headers={
                "Idempotency-Key": "dec-1",
                "If-Match": f'"{match.etag}"',
                "X-Forwarded-For": "203.0.113.9, 10.0.0.1",
            },
        )
    )
    assert first.status_code == 201
    payload = _body(first)
    assert payload["matchStatus"] == "approved"
    assert payload["version"] == 1
    replay = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve", "comment": "ignored"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "dec-1", "If-Match": "stale"},
        )
    )
    assert replay.status_code == 200
    assert _body(replay)["decisionId"] == payload["decisionId"]
    messages = queue.of("decision-events")
    assert len(messages) == 1
    assert messages[0]["eventType"] == "DecisionCreated"
    assert "comment" not in messages[0]
    assert messages[0]["decisionId"] == payload["decisionId"]
    audits = [
        item for item in store.list_audit(USER, match_id=match.id, event_type="DECISION") if item.payload.get("ip")
    ]
    assert audits[0].payload["ip"] == "203.0.113.9"
    assert audits[0].payload["before"] == "PENDING"
    assert audits[0].payload["after"] == "APPROVED"


def test_conflicting_decision_is_409_without_overwrite(svc, store):
    match = _seed(store)
    routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "a", "If-Match": match.etag},
        )
    )
    current = store.get_match(match.id, user_id=USER)
    conflict = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "reject"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "b", "If-Match": current.etag},
        )
    )
    assert conflict.status_code == 409


def test_overwrite_within_24h_appends_history(svc, store):
    match = _seed(store)
    first = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "a", "If-Match": match.etag},
        )
    )
    current = store.get_match(match.id, user_id=USER)
    second = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "reject", "overwrite": True, "comment": "changed"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "b", "If-Match": current.etag},
        )
    )
    assert second.status_code == 201
    assert _body(second)["matchStatus"] == "rejected"
    assert _body(second)["version"] == 2
    history = routes.decision_history(
        _req("GET", "http://localhost/api/v1/decisions/history", params={"matchId": match.id})
    )
    items = _body(history)["items"]
    assert [item["decision"] for item in items] == ["approve", "reject"]
    assert items[1]["supersedesDecisionId"] == _body(first)["decisionId"]


def test_overwrite_after_24h_is_409(svc, store, clock):
    match = _seed(store)
    routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "a", "If-Match": match.etag},
        )
    )
    clock.advance(hours=25)
    current = store.get_match(match.id, user_id=USER)
    late = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "reject", "overwrite": True},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "b", "If-Match": current.etag},
        )
    )
    assert late.status_code == 409


def test_comment_too_long_is_400(svc, store):
    match = _seed(store)
    resp = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "approve", "comment": "x" * (MAX_COMMENT_CHARS + 1)},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "k", "If-Match": match.etag},
        )
    )
    assert resp.status_code == 400


def test_saved_jobs_queue(svc, store):
    pending = _seed(store, job_id="saved-1", source="saved")
    decided = _seed(store, job_id="saved-2", source="saved", resume_id="resume-2")
    routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{decided.id}/decision",
            json_body={"decision": "reject"},
            route={"matchId": decided.id},
            headers={"Idempotency-Key": "s2", "If-Match": decided.etag},
        )
    )
    _seed(store, job_id="ai-1", source="ai", resume_id="resume-3")
    waiting = routes.list_saved_jobs(
        _req("GET", "http://localhost/api/v1/queue/saved-jobs", params={"status": "awaiting_decision"})
    )
    assert {item["jobId"] for item in _body(waiting)["items"]} == {"saved-1"}
    assert _body(waiting)["items"][0]["queueItemId"] == pending.id
    done = routes.list_saved_jobs(
        _req("GET", "http://localhost/api/v1/queue/saved-jobs", params={"status": "decided"})
    )
    assert {item["jobId"] for item in _body(done)["items"]} == {"saved-2"}


def test_history_requires_exactly_one_filter(svc, store):
    match = _seed(store)
    empty = routes.decision_history(_req("GET", "http://localhost/api/v1/decisions/history"))
    assert empty.status_code == 400
    both = routes.decision_history(
        _req(
            "GET",
            "http://localhost/api/v1/decisions/history",
            params={"matchId": match.id, "jobId": "job-1"},
        )
    )
    assert both.status_code == 400
    by_job = routes.decision_history(
        _req("GET", "http://localhost/api/v1/decisions/history", params={"jobId": "job-1"})
    )
    assert by_job.status_code == 200
    assert _body(by_job)["items"] == []


def test_reopen_returns_match_to_pending(svc, store):
    match = _seed(store)
    decided = routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/decision",
            json_body={"decision": "reject", "comment": "too junior"},
            route={"matchId": match.id},
            headers={"Idempotency-Key": "r1", "If-Match": match.etag},
        )
    )
    assert decided.status_code == 201
    resp = routes.reopen_match(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{match.id}/reopen",
            route={"matchId": match.id},
        )
    )
    assert resp.status_code == 200
    body = _body(resp)
    assert body["status"] == "pending"
    assert body["matchId"] == match.id
    history = routes.decision_history(
        _req("GET", "http://localhost/api/v1/decisions/history", params={"matchId": match.id})
    )
    assert len(_body(history)["items"]) == 1


def test_queue_worker_poison_after_five(svc):
    payload = {"eventType": "DecisionCreated", "userId": USER, "decisionId": "d1", "matchId": "m1"}
    svc.process_decision_event(payload, dequeue_count=1)
    assert svc.processed_decisions == 1
    svc.process_decision_event(payload, dequeue_count=6)
    assert svc.poisoned == 1
    assert svc.processed_decisions == 1


def test_saved_jobs_sort_by_title_and_created_at(svc, store):
    zebra = _seed(store, job_id="saved-b", source="saved", job_title="Zebra Role", company="Beta")
    alpha = _seed(store, job_id="saved-a", source="saved", job_title="Alpha Role", company="Acme", resume_id="resume-2")
    by_title = routes.list_saved_jobs(
        _req(
            "GET",
            "http://localhost/api/v1/queue/saved-jobs",
            params={"status": "awaiting_decision", "sort": "jobTitle", "order": "asc"},
        )
    )
    assert [_item["jobTitle"] for _item in _body(by_title)["items"]] == ["Alpha Role", "Zebra Role"]
    by_created = routes.list_saved_jobs(
        _req(
            "GET",
            "http://localhost/api/v1/queue/saved-jobs",
            params={"status": "awaiting_decision", "sort": "createdAt", "order": "desc"},
        )
    )
    newest_first = [
        match.job_id
        for match in sorted([zebra, alpha], key=lambda match: match.created_at, reverse=True)
    ]
    assert [_item["jobId"] for _item in _body(by_created)["items"]] == newest_first
    bad = routes.list_saved_jobs(
        _req("GET", "http://localhost/api/v1/queue/saved-jobs", params={"sort": "score"})
    )
    assert bad.status_code == 400


def test_list_decisions_filters_and_pagination(svc, store):
    first = _seed(store, job_id="job-a", job_title="A")
    second = _seed(store, job_id="job-b", job_title="B", resume_id="resume-2")
    routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{first.id}/decision",
            json_body={"decision": "approve"},
            route={"matchId": first.id},
            headers={"Idempotency-Key": "d-a", "If-Match": first.etag},
        )
    )
    routes.create_decision(
        _req(
            "POST",
            f"http://localhost/api/v1/matches/{second.id}/decision",
            json_body={"decision": "reject"},
            route={"matchId": second.id},
            headers={"Idempotency-Key": "d-b", "If-Match": second.etag},
        )
    )
    listed = routes.list_decisions(_req("GET", "http://localhost/api/v1/decisions"))
    assert listed.status_code == 200
    decisions = [item["decision"] for item in _body(listed)["items"]]
    assert decisions[:2] == ["reject", "approve"]
    by_job = routes.list_decisions(
        _req("GET", "http://localhost/api/v1/decisions", params={"jobId": "job-a"})
    )
    assert [item["matchId"] for item in _body(by_job)["items"]] == [first.id]
    rejected = routes.list_decisions(
        _req("GET", "http://localhost/api/v1/decisions", params={"decision": "reject"})
    )
    assert [item["decision"] for item in _body(rejected)["items"]] == ["reject"]
    for index in range(9):
        extra = _seed(
            store,
            job_id=f"job-extra-{index}",
            resume_id=f"resume-extra-{index}",
            job_title=f"Extra {index}",
        )
        routes.create_decision(
            _req(
                "POST",
                f"http://localhost/api/v1/matches/{extra.id}/decision",
                json_body={"decision": "approve"},
                route={"matchId": extra.id},
                headers={"Idempotency-Key": f"d-extra-{index}", "If-Match": extra.etag},
            )
        )
    paged = routes.list_decisions(
        _req("GET", "http://localhost/api/v1/decisions", params={"pageSize": "10"})
    )
    body = _body(paged)
    assert paged.status_code == 200
    assert len(body["items"]) == 10
    assert "continuationToken" in body
    page2 = routes.list_decisions(
        _req(
            "GET",
            "http://localhost/api/v1/decisions",
            params={"pageSize": "10", "continuation": body["continuationToken"]},
        )
    )
    assert len(_body(page2)["items"]) == 1
    seen = {item["decisionId"] for item in body["items"]} | {item["decisionId"] for item in _body(page2)["items"]}
    assert len(seen) == 11


def test_decide_enqueues_learning_event_with_threshold(svc, store, queue):
    from app.settings.memory import InMemorySettingsStore
    from app.settings.queues import InMemoryJobQueue as SettingsQueue
    from app.settings.runtime import set_service as set_settings_service
    from app.settings.service import SettingsService

    settings_store = InMemorySettingsStore()
    settings_store.get_or_create_settings(USER)
    settings_store.update_settings(USER, actor_id=USER, expected_version=1, match_threshold=80)
    set_settings_service(SettingsService(store=settings_store, queue=SettingsQueue()))
    try:
        match = _seed(store)
        resp = routes.create_decision(
            _req(
                "POST",
                f"http://localhost/api/v1/matches/{match.id}/decision",
                json_body={"decision": "approve"},
                route={"matchId": match.id},
                headers={"Idempotency-Key": "learn-1", "If-Match": match.etag},
            )
        )
        assert resp.status_code == 201
        events = queue.of("learning-decisions")
        assert len(events) == 1
        payload = events[0]
        assert payload["eventType"] == "LearningDecisionLogged"
        assert payload["userId"] == USER
        assert payload["jobId"] == "job-1"
        assert payload["resumeId"] == "resume-1"
        assert payload["matchId"] == match.id
        assert payload["decisionId"] == _body(resp)["decisionId"]
        assert payload["score"] == 88.0
        assert payload["threshold"] == 0.8
        assert payload["outcome"] == "approve"
        assert payload["idempotency_key"] == payload["decisionId"]
        assert payload["occurredAt"]
        assert svc.learning_events == events
        assert len(queue.of("decision-events")) == 1
    finally:
        set_settings_service(None)


def test_reopen_sends_learning_undo(svc, store, queue):
    from app.learning.memory import InMemoryLearningStore
    from app.learning.queues import InMemoryJobQueue as LearningQueue
    from app.learning.runtime import set_service as set_learning
    from app.learning.service import LearningService

    learning_store = InMemoryLearningStore(seed=False)
    set_learning(LearningService(store=learning_store, queue=LearningQueue(), local_mode=False))
    try:
        match = _seed(store)
        decided = routes.create_decision(
            _req(
                "POST",
                f"http://localhost/api/v1/matches/{match.id}/decision",
                json_body={"decision": "approve"},
                route={"matchId": match.id},
                headers={"Idempotency-Key": "undo-1", "If-Match": match.etag},
            )
        )
        assert decided.status_code == 201
        assert learning_store.get_decision_by_rec(USER, match.id).decision == "approve"
        reopened = routes.reopen_match(
            _req(
                "POST",
                f"http://localhost/api/v1/matches/{match.id}/reopen",
                route={"matchId": match.id},
            )
        )
        assert reopened.status_code == 200
        assert _body(reopened)["status"] == "pending"
        assert learning_store.get_decision_by_rec(USER, match.id).decision == "skip"
        undo_events = [item for item in queue.of("learning-decisions") if item.get("outcome") == "undo"]
        approve_events = [item for item in queue.of("learning-decisions") if item.get("outcome") == "approve"]
        assert len(undo_events) == 1
        assert undo_events[0]["matchId"] == match.id
        assert approve_events[0]["decisionId"] == undo_events[0]["decisionId"]
        assert undo_events[0]["idempotency_key"] == approve_events[0]["idempotency_key"]
        stored = learning_store.get_decision_by_rec(USER, match.id)
        assert stored.idempotency_key == f"{undo_events[0]['decisionId']}-undo"
        assert stored.idempotency_key != undo_events[0]["decisionId"]
    finally:
        set_learning(None)

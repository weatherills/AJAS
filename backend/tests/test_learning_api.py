"""Learning Loop Backend PRD — HTTP API, idempotency, tuning, metrics."""

from __future__ import annotations

import json

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import learning_loop as routes
from app.learning.constants import GLOBAL_CONFIG_ID
from app.learning.keys import utc_now
from app.learning.memory import InMemoryLearningStore
from app.learning.models import Recommendation
from app.learning.queues import InMemoryJobQueue
from app.learning.runtime import set_service
from app.learning.service import LearningService

USER = "user-1"


@pytest.fixture
def store():
    return InMemoryLearningStore(seed=False)


@pytest.fixture
def queue():
    return InMemoryJobQueue()


@pytest.fixture
def svc(monkeypatch, store, queue):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    get_settings.cache_clear()
    service = LearningService(store=store, queue=queue, local_mode=False)
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
    headers: dict | None = None,
    admin: bool = False,
) -> func.HttpRequest:
    hdrs = dict(headers or {})
    raw = b""
    if user:
        hdrs["Authorization"] = f"Bearer {user}"
    if admin:
        hdrs["X-Admin"] = "1"
    if json_body is not None:
        hdrs["Content-Type"] = "application/json"
        raw = json.dumps(json_body).encode()
    return func.HttpRequest(
        method=method,
        url=url,
        headers=hdrs,
        params=params or {},
        route_params={},
        body=raw,
    )


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    return json.loads(raw) if raw else None


def _seed_rec(store, rec_id="rec-1", score=0.8):
    now = utc_now()
    return store.upsert_recommendation(
        Recommendation(
            id=rec_id,
            user_id=USER,
            job_id="job-1",
            score=score,
            weight_config_id=GLOBAL_CONFIG_ID,
            threshold=0.7,
            generated_at=now,
            model_version="learning-v1",
        )
    )


def test_function_app_registers_learning_routes(function_names):
    assert "log_learning_decision" in function_names
    assert "get_learning_params" in function_names
    assert "tune_learning" in function_names
    assert "get_learning_metrics" in function_names
    assert "learning_decisions_job" in function_names
    assert "health" in function_names


def test_unauthenticated_is_401(svc):
    resp = routes.get_learning_params(_req("GET", "http://localhost/api/v1/learning/params", user=None))
    assert resp.status_code == 401


def test_unknown_recommendation_is_404(svc):
    resp = routes.log_learning_decision(
        _req(
            "POST",
            "http://localhost/api/v1/learning/decisions",
            json_body={
                "recommendation_id": "missing",
                "job_id": "job-1",
                "decision": "approve",
                "model_version": "v1",
                "score_at_decision": 0.8,
                "idempotency_key": "k1",
            },
        )
    )
    assert resp.status_code == 404


def test_comment_too_long_is_400(svc, store):
    _seed_rec(store)
    resp = routes.log_learning_decision(
        _req(
            "POST",
            "http://localhost/api/v1/learning/decisions",
            json_body={
                "recommendation_id": "rec-1",
                "job_id": "job-1",
                "decision": "approve",
                "model_version": "v1",
                "score_at_decision": 0.8,
                "idempotency_key": "k1",
                "comment": "x" * 1001,
            },
        )
    )
    assert resp.status_code == 400


def test_decision_rate_limit_is_429(svc, store):
    svc._rate_limit = LearningService._rate_limit.__get__(svc, LearningService)
    for idx in range(10):
        rec_id = f"rate-{idx}"
        _seed_rec(store, rec_id=rec_id)
        resp = routes.log_learning_decision(
            _req(
                "POST",
                "http://localhost/api/v1/learning/decisions",
                json_body={
                    "recommendation_id": rec_id,
                    "job_id": f"job-r-{idx}",
                    "decision": "approve",
                    "model_version": "v1",
                    "score_at_decision": 0.8,
                    "idempotency_key": f"rate-{idx}",
                },
            )
        )
        assert resp.status_code == 201
    _seed_rec(store, rec_id="rate-11")
    limited = routes.log_learning_decision(
        _req(
            "POST",
            "http://localhost/api/v1/learning/decisions",
            json_body={
                "recommendation_id": "rate-11",
                "job_id": "job-r-11",
                "decision": "approve",
                "model_version": "v1",
                "score_at_decision": 0.8,
                "idempotency_key": "rate-11",
            },
        )
    )
    assert limited.status_code == 429
    assert limited.headers.get("Retry-After") == "1"


def test_log_decision_201_and_idempotent_200(svc, store, queue):
    _seed_rec(store)
    payload = {
        "recommendation_id": "rec-1",
        "job_id": "job-1",
        "decision": "approve",
        "model_version": "v1",
        "score_at_decision": 0.82,
        "idempotency_key": "same",
        "comment": "good fit",
    }
    first = routes.log_learning_decision(_req("POST", "http://localhost/api/v1/learning/decisions", json_body=payload))
    assert first.status_code == 201
    decision_id = _body(first)["decision_id"]
    replay = routes.log_learning_decision(_req("POST", "http://localhost/api/v1/learning/decisions", json_body=payload))
    assert replay.status_code == 200
    assert _body(replay)["decision_id"] == decision_id
    assert len(store.list_decisions(USER)) == 1


def test_prd_alias_post_decisions(svc, store):
    _seed_rec(store)
    resp = routes.log_learning_decision_prd(
        _req(
            "POST",
            "http://localhost/api/v1/decisions",
            json_body={
                "recommendation_id": "rec-1",
                "job_id": "job-1",
                "decision": "reject",
                "model_version": "v1",
                "score_at_decision": 88,
                "idempotency_key": "prd-1",
            },
        )
    )
    assert resp.status_code == 201


def test_ingest_review_event(svc, store):
    svc.ingest_event(
        {
            "eventType": "LearningDecisionLogged",
            "userId": USER,
            "jobId": "job-1",
            "matchId": "match-99",
            "decisionId": "dec-99",
            "score": 88.0,
            "threshold": 0.8,
            "outcome": "approve",
            "occurredAt": utc_now(),
        }
    )
    rec = store.get_recommendation("match-99")
    assert rec.score == pytest.approx(0.88)
    assert store.get_decision_by_rec(USER, "match-99").decision == "approve"


def test_ingest_undo_flips_prior_decision_to_skip(svc, store):
    payload = {
        "eventType": "LearningDecisionLogged",
        "userId": USER,
        "jobId": "job-1",
        "matchId": "match-undo",
        "decisionId": "dec-undo",
        "score": 90.0,
        "threshold": 0.7,
        "occurredAt": utc_now(),
    }
    svc.ingest_event({**payload, "outcome": "approve"})
    approved = store.get_decision_by_rec(USER, "match-undo")
    assert approved.decision == "approve"
    assert approved.idempotency_key == "dec-undo"
    svc.ingest_event({**payload, "outcome": "undo"})
    undone = store.get_decision_by_rec(USER, "match-undo")
    assert undone.decision == "skip"
    assert undone.idempotency_key == "dec-undo-undo"
    rec = store.get_recommendation("match-undo")
    assert rec.status == "pending"
    svc.ingest_event({**payload, "outcome": "undo"})
    assert store.get_decision_by_rec(USER, "match-undo").decision == "skip"
    assert store.get_decision_by_rec(USER, "match-undo").idempotency_key == "dec-undo-undo"


def test_tune_requires_admin(svc):
    resp = routes.tune_learning(_req("POST", "http://localhost/api/v1/learning/tune", json_body={}))
    assert resp.status_code == 403


def test_tune_keeps_global_below_min_samples(svc, store):
    _seed_rec(store)
    routes.log_learning_decision(
        _req(
            "POST",
            "http://localhost/api/v1/learning/decisions",
            json_body={
                "recommendation_id": "rec-1",
                "job_id": "job-1",
                "decision": "approve",
                "model_version": "v1",
                "score_at_decision": 0.8,
                "idempotency_key": "one",
            },
        )
    )
    resp = routes.tune_learning(_req("POST", "http://localhost/api/v1/learning/tune", json_body={"user_id": USER}, admin=True))
    assert resp.status_code == 202
    params = _body(routes.get_learning_params(_req("GET", "http://localhost/api/v1/learning/params")))
    assert params["source"] == "global"
    assert params["sample_size"] == 1


def test_tune_personalizes_with_enough_samples(svc, store):
    svc._rate_limit = lambda _user_id: None  # bulk seed; production cap is 10/s
    for idx in range(22):
        rec_id = f"rec-{idx}"
        _seed_rec(store, rec_id=rec_id, score=0.85 if idx < 18 else 0.4)
        routes.log_learning_decision(
            _req(
                "POST",
                "http://localhost/api/v1/learning/decisions",
                json_body={
                    "recommendation_id": rec_id,
                    "job_id": f"job-{idx}",
                    "decision": "approve" if idx < 18 else "reject",
                    "model_version": "v1",
                    "score_at_decision": 0.85 if idx < 18 else 0.4,
                    "idempotency_key": f"k-{idx}",
                },
            )
        )
    resp = routes.tune_learning(
        _req(
            "POST",
            "http://localhost/api/v1/learning/tune",
            json_body={"user_id": USER, "min_samples": 20, "force_activate": True},
            admin=True,
        )
    )
    assert resp.status_code == 202
    params = _body(routes.get_learning_params(_req("GET", "http://localhost/api/v1/learning/params")))
    assert params["source"] == "personalized"
    assert params["sample_size"] >= 20
    assert abs(params["weights"]["keyword"] + params["weights"]["semantic"] - 1) < 0.02


def test_metrics_self_and_global_forbidden(svc, store):
    store.seed_demo(USER)
    self_resp = routes.get_learning_metrics(_req("GET", "http://localhost/api/v1/metrics", params={"scope": "self", "period": "7d"}))
    assert self_resp.status_code == 200
    body = _body(self_resp)
    assert "precision_proxy" in body
    assert "recall_proxy" in body
    denied = routes.get_learning_metrics(_req("GET", "http://localhost/api/v1/metrics", params={"scope": "global"}))
    assert denied.status_code == 403
    allowed = routes.get_learning_metrics(
        _req("GET", "http://localhost/api/v1/metrics", params={"scope": "global", "period": "30d"}, admin=True)
    )
    assert allowed.status_code == 200


def test_manual_strictness(svc):
    patched = routes.patch_learning_params(
        _req("PATCH", "http://localhost/api/v1/learning/params", json_body={"tuningMode": "manual", "strictness": 0})
    )
    assert patched.status_code == 200
    body = _body(patched)
    assert body["tuningMode"] == "manual"
    assert body["strictness"] == 0
    assert body["score_threshold"] == pytest.approx(0.8)


def test_comment_is_encrypted_at_rest(svc, store):
    _seed_rec(store)
    routes.log_learning_decision(
        _req(
            "POST",
            "http://localhost/api/v1/learning/decisions",
            json_body={
                "recommendation_id": "rec-1",
                "job_id": "job-1",
                "decision": "approve",
                "model_version": "v1",
                "score_at_decision": 0.8,
                "idempotency_key": "enc-1",
                "comment": "secret recruiter note",
            },
        )
    )
    row = store.get_decision_by_rec(USER, "rec-1")
    assert row.comment_enc.startswith("enc.")
    assert "secret recruiter note" not in row.comment_enc


def test_stale_recommendation_is_404(svc, store):
    from app.learning.keys import days_ago

    rec = _seed_rec(store)
    rec.generated_at = days_ago(91)
    store._recs[rec.id] = rec
    resp = routes.log_learning_decision(
        _req(
            "POST",
            "http://localhost/api/v1/learning/decisions",
            json_body={
                "recommendation_id": "rec-1",
                "job_id": "job-1",
                "decision": "approve",
                "model_version": "v1",
                "score_at_decision": 0.8,
                "idempotency_key": "stale",
            },
        )
    )
    assert resp.status_code == 404


def test_admin_can_read_other_user_params(svc, store):
    store.get_or_create_params("other-user")
    denied = routes.get_learning_params(
        _req("GET", "http://localhost/api/v1/learning/params", params={"user_id": "other-user"})
    )
    assert denied.status_code == 403
    allowed = routes.get_learning_params(
        _req("GET", "http://localhost/api/v1/learning/params", params={"user_id": "other-user"}, admin=True)
    )
    assert allowed.status_code == 200
    assert _body(allowed)["source"] == "global"


def test_metrics_include_period_buckets(svc, store):
    store.seed_demo(USER)
    body = _body(routes.get_learning_metrics(_req("GET", "http://localhost/api/v1/metrics", params={"period": "7d"})))
    assert isinstance(body["buckets"], list)
    assert len(body["buckets"]) == 2
    assert "precision_proxy" in body["buckets"][0]
    assert "recall_proxy" in body["buckets"][0]


def test_tune_rolls_back_when_precision_drops(svc, store):
    from app.learning.keys import days_ago

    svc._rate_limit = lambda _user_id: None
    paused = store.get_or_create_params(USER)
    paused.tuning_mode = "manual"
    store.put_params(paused)
    now_prior = days_ago(10)
    now_current = days_ago(2)
    for idx in range(20):
        rec_id = f"prior-{idx}"
        rec = _seed_rec(store, rec_id=rec_id, score=0.9)
        rec.generated_at = now_prior
        store._recs[rec.id] = rec
        routes.log_learning_decision(
            _req(
                "POST",
                "http://localhost/api/v1/learning/decisions",
                json_body={
                    "recommendation_id": rec_id,
                    "job_id": f"job-p-{idx}",
                    "decision": "approve",
                    "model_version": "v1",
                    "score_at_decision": 0.9,
                    "idempotency_key": f"prior-{idx}",
                },
            )
        )
        row = store.get_decision_by_rec(USER, rec_id)
        row.updated_at = now_prior
        store.put_decision(row)
    for idx in range(20):
        rec_id = f"curr-{idx}"
        rec = _seed_rec(store, rec_id=rec_id, score=0.9)
        rec.generated_at = now_current
        store._recs[rec.id] = rec
        routes.log_learning_decision(
            _req(
                "POST",
                "http://localhost/api/v1/learning/decisions",
                json_body={
                    "recommendation_id": rec_id,
                    "job_id": f"job-c-{idx}",
                    "decision": "reject",
                    "model_version": "v1",
                    "score_at_decision": 0.9,
                    "idempotency_key": f"curr-{idx}",
                },
            )
        )
        row = store.get_decision_by_rec(USER, rec_id)
        row.updated_at = now_current
        store.put_decision(row)
    params = store.get_or_create_params(USER)
    params.tuning_mode = "auto"
    params.source = "personalized"
    params.weights = {"keyword": 0.55, "semantic": 0.45}
    params.previous = {"weights": {"keyword": 0.55, "semantic": 0.45}, "score_threshold": 0.7}
    store.put_params(params)
    resp = routes.tune_learning(
        _req(
            "POST",
            "http://localhost/api/v1/learning/tune",
            json_body={"user_id": USER, "min_samples": 20, "force_activate": True},
            admin=True,
        )
    )
    assert resp.status_code == 202
    body = _body(routes.get_learning_params(_req("GET", "http://localhost/api/v1/learning/params")))
    assert body["source"] == "global"
    events = store.list_events(USER)
    assert any(event.rolled_back for event in events)


def test_tune_keeps_weekly_shown_floor(svc, store):
    svc._rate_limit = lambda _user_id: None
    paused = store.get_or_create_params(USER)
    paused.tuning_mode = "manual"
    store.put_params(paused)
    for idx in range(20):
        rec_id = f"floor-{idx}"
        _seed_rec(store, rec_id=rec_id, score=0.65)
        routes.log_learning_decision(
            _req(
                "POST",
                "http://localhost/api/v1/learning/decisions",
                json_body={
                    "recommendation_id": rec_id,
                    "job_id": f"job-f-{idx}",
                    "decision": "reject",
                    "model_version": "v1",
                    "score_at_decision": 0.65,
                    "idempotency_key": f"floor-{idx}",
                },
            )
        )
    resp = routes.tune_learning(
        _req(
            "POST",
            "http://localhost/api/v1/learning/tune",
            json_body={"user_id": USER, "min_samples": 20, "force_activate": True},
            admin=True,
        )
    )
    assert resp.status_code == 202
    params = _body(routes.get_learning_params(_req("GET", "http://localhost/api/v1/learning/params")))
    # Low approval rate would raise the threshold, but the 10/week shown floor holds it down.
    assert params["score_threshold"] <= 0.70


def test_delete_user_data_cascades(svc, store):
    store.seed_demo(USER)
    assert store.list_decisions(USER)
    svc.delete_user_data(USER)
    assert store.list_decisions(USER) == []
    assert store.list_recommendations(USER) == []
    created = store.get_or_create_params(USER)
    assert created.source == "global"
    assert created.sample_size == 0

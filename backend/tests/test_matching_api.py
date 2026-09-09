"""Matching & Ranking Backend PRD — HTTP API, scoring, queues."""

from __future__ import annotations

import json

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import matching as routes
from app.matching.embedder import HashEmbedder
from app.matching.memory import InMemoryMatchingStore
from app.matching.queues import InMemoryJobQueue
from app.matching.runtime import set_service
from app.matching.scoring import cosine_similarity, keyword_score
from app.matching.service import MatchingService
from app.matching.texts import MemoryTextLoader

USER = "user-1"
OTHER = "user-2"
RESUME = "python azure cosmos functions kubernetes terraform"
HIGH_JOB = "Title: python azure cosmos functions kubernetes terraform\nSkills: python azure cosmos"
LOW_JOB = "Title: Baker\nCompany: Cakes\nSkills: frosting pastry whisk\nBake cakes daily with fondant"
MID_JOB = "Title: Platform Engineer\nSkills: python baking\nShip services"


class ScriptedEmbedder:
    def __init__(self, table: dict[str, list[float]] | None = None, default: list[float] | None = None) -> None:
        self.table = table or {}
        self.default = default or [1.0, 0.0]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(self.table.get(text, self.default)) for text in texts]


class BoomExplainer:
    def explain(self, **_kwargs) -> str:
        raise RuntimeError("explainer down")


class Clock:
    def __init__(self, start: float = 1_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def store():
    return InMemoryMatchingStore()


@pytest.fixture
def queue():
    return InMemoryJobQueue()


@pytest.fixture
def loader():
    return MemoryTextLoader()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def svc(monkeypatch, store, queue, loader, clock):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = MatchingService(
        store=store,
        queue=queue,
        embedder=HashEmbedder(),
        text_loader=loader,
        clock=clock,
    )
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
) -> func.HttpRequest:
    hdrs = dict(headers or {})
    body = b""
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


def test_function_app_registers_matching_routes(function_names):
    assert "compute_match" in function_names
    assert "rank_matches" in function_names
    assert "list_match_results" in function_names
    assert "get_operation" in function_names
    assert "cancel_operation" in function_names
    assert "match_compute_job" in function_names
    assert "health" in function_names


def test_unauthenticated_is_401(svc):
    resp = routes.compute_match(_req("POST", "http://localhost/api/v1/matches/compute", user=None, json_body={}))
    assert resp.status_code == 401
    assert _body(resp)["error"]["code"] == "UNAUTHENTICATED"


def test_empty_text_is_invalid_input(svc):
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": "   ", "jobText": LOW_JOB},
        )
    )
    assert resp.status_code == 400
    assert _body(resp)["error"]["code"] == "INVALID_INPUT"


def test_missing_resume_id_is_not_found(svc):
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeId": "missing", "jobText": LOW_JOB},
        )
    )
    assert resp.status_code == 404


def test_payload_too_large_is_413(svc):
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": "python " * 20_000, "jobText": LOW_JOB},
        )
    )
    assert resp.status_code == 413
    assert _body(resp)["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_short_input_still_computes(svc):
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": "python azure", "jobText": "Title: baker"},
        )
    )
    assert resp.status_code == 200
    assert svc.low_confidence_events >= 1
    body = _body(resp)
    assert "score" in body
    assert body["persisted"] is False
    assert "matchId" not in body


def test_high_score_persists_and_low_score_does_not(svc):
    high = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": HIGH_JOB, "jobId": "job-high"},
        )
    )
    low = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": LOW_JOB, "jobId": "job-low"},
        )
    )
    assert high.status_code == 200
    assert low.status_code == 200
    high_body = _body(high)
    low_body = _body(low)
    assert high_body["score"] >= 70
    assert high_body["persisted"] is True
    assert high_body["matchId"]
    assert low_body["score"] < 70
    assert low_body["persisted"] is False
    assert "matchId" not in low_body
    listed = _body(routes.list_match_results(_req("GET", "http://localhost/api/v1/match-results")))
    assert [item["jobId"] for item in listed["items"]] == ["job-high"]


def test_weights_keyword_semantic_0_4_0_6(monkeypatch, store, queue, clock):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    identical = ScriptedEmbedder(default=[1.0, 0.0])
    orthogonal = ScriptedEmbedder(
        table={RESUME: [1.0, 0.0], HIGH_JOB: [0.0, 1.0]},
        default=[0.0, 1.0],
    )
    keyword_only = MatchingService(store=store, queue=queue, embedder=orthogonal, clock=clock)
    set_service(keyword_only)
    keyword_resp = _body(
        routes.compute_match(
            _req(
                "POST",
                "http://localhost/api/v1/matches/compute",
                json_body={"resumeText": RESUME, "jobText": HIGH_JOB, "threshold": 0},
            )
        )
    )
    semantic_store = InMemoryMatchingStore()
    semantic_only = MatchingService(store=semantic_store, queue=queue, embedder=identical, clock=clock)
    set_service(semantic_only)
    semantic_resp = _body(
        routes.compute_match(
            _req(
                "POST",
                "http://localhost/api/v1/matches/compute",
                json_body={"resumeText": RESUME, "jobText": LOW_JOB, "threshold": 0},
            )
        )
    )
    set_service(None)
    get_settings.cache_clear()
    assert keyword_resp["breakdown"]["keyword"] == 100.0
    assert keyword_resp["breakdown"]["semantic"] == 0.0
    assert keyword_resp["score"] == 40.0
    assert keyword_resp["breakdown"]["weights"] == {"keyword": 0.4, "semantic": 0.6}
    assert semantic_resp["breakdown"]["keyword"] == 0.0
    assert semantic_resp["breakdown"]["semantic"] == 100.0
    assert semantic_resp["score"] == 60.0


def test_threshold_override_persists_below_default(svc):
    defaulted = _body(
        routes.compute_match(
            _req(
                "POST",
                "http://localhost/api/v1/matches/compute",
                json_body={"resumeText": RESUME, "jobText": MID_JOB},
            )
        )
    )
    overridden = _body(
        routes.compute_match(
            _req(
                "POST",
                "http://localhost/api/v1/matches/compute",
                json_body={"resumeText": RESUME, "jobText": MID_JOB, "threshold": 10, "jobId": "mid"},
            )
        )
    )
    assert defaulted["thresholdUsed"] == 70
    assert overridden["thresholdUsed"] == 10
    if defaulted["score"] < 70:
        assert defaulted["persisted"] is False
    assert overridden["score"] >= 10
    assert overridden["persisted"] is True
    assert overridden["matchId"]


def test_idempotency_key_returns_same_match(svc):
    payload = {"resumeText": RESUME, "jobText": HIGH_JOB, "jobId": "job-idem"}
    first = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body=payload,
            headers={"Idempotency-Key": "k-1"},
        )
    )
    second = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body=payload,
            headers={"Idempotency-Key": "k-1"},
        )
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert _body(first)["matchId"] == _body(second)["matchId"]
    listed = _body(routes.list_match_results(_req("GET", "http://localhost/api/v1/match-results")))
    assert len(listed["items"]) == 1


def test_idempotency_key_conflict_on_different_body(svc):
    routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": HIGH_JOB},
            headers={"Idempotency-Key": "k-2"},
        )
    )
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": LOW_JOB},
            headers={"Idempotency-Key": "k-2"},
        )
    )
    assert resp.status_code == 409


def test_rank_sorts_desc_and_forces_async_over_ten(svc):
    jobs = [f"Title: python role {i}\nSkills: python azure" for i in range(3)]
    jobs.append(LOW_JOB)
    sync = routes.rank_matches(
        _req(
            "POST",
            "http://localhost/api/v1/matches/rank",
            json_body={"resumeText": RESUME, "jobTexts": jobs},
        )
    )
    assert sync.status_code == 200
    scores = [item["score"] for item in _body(sync)["results"]]
    assert scores == sorted(scores, reverse=True)
    many = [f"Title: python {i}\nSkills: python" for i in range(11)]
    async_resp = routes.rank_matches(
        _req(
            "POST",
            "http://localhost/api/v1/matches/rank",
            json_body={"resumeText": RESUME, "jobTexts": many},
        )
    )
    assert async_resp.status_code == 202
    operation_id = _body(async_resp)["operationId"]
    svc.drain()
    op = routes.get_operation(
        _req(
            "GET",
            f"http://localhost/api/v1/operations/{operation_id}",
            route={"operationId": operation_id},
        )
    )
    body = _body(op)
    assert op.status_code == 200
    assert body["status"] == "completed"
    assert len(body["results"]) == 11
    result_scores = [item["score"] for item in body["results"]]
    assert result_scores == sorted(result_scores, reverse=True)


def test_rank_zips_job_ids_with_aligned_texts(svc):
    resp = routes.rank_matches(
        _req(
            "POST",
            "http://localhost/api/v1/matches/rank",
            json_body={
                "resumeText": RESUME,
                "jobIds": ["high", "low"],
                "jobTexts": [HIGH_JOB, LOW_JOB],
            },
        )
    )
    assert resp.status_code == 200
    rows = _body(resp)["results"]
    assert len(rows) == 2
    by_id = {item["jobId"]: item for item in rows}
    assert by_id["high"]["score"] > by_id["low"]["score"]


def test_rank_rejects_misaligned_job_ids_and_texts(svc):
    resp = routes.rank_matches(
        _req(
            "POST",
            "http://localhost/api/v1/matches/rank",
            json_body={"resumeText": RESUME, "jobIds": ["a"], "jobTexts": [HIGH_JOB, LOW_JOB]},
        )
    )
    assert resp.status_code == 400


def test_rank_rejects_over_one_thousand_pairs(svc):
    resp = routes.rank_matches(
        _req(
            "POST",
            "http://localhost/api/v1/matches/rank",
            json_body={"resumeText": RESUME, "jobTexts": ["baker cake"] * 1001},
        )
    )
    assert resp.status_code == 400


def test_list_matches_is_user_owned(svc):
    routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": HIGH_JOB, "jobId": "owned"},
        )
    )
    mine = _body(routes.list_match_results(_req("GET", "http://localhost/api/v1/match-results")))
    theirs = _body(routes.list_match_results(_req("GET", "http://localhost/api/v1/match-results", user=OTHER)))
    assert len(mine["items"]) == 1
    assert theirs["items"] == []
    filtered = _body(
        routes.list_match_results(_req("GET", "http://localhost/api/v1/match-results", params={"jobId": "owned", "minScore": "70"}))
    )
    assert len(filtered["items"]) == 1


def test_sync_rate_limit_is_429(svc, clock):
    payload = {"resumeText": RESUME, "jobText": LOW_JOB}
    last = None
    for _ in range(60):
        last = routes.compute_match(_req("POST", "http://localhost/api/v1/matches/compute", json_body=payload))
        assert last.status_code == 200
    limited = routes.compute_match(_req("POST", "http://localhost/api/v1/matches/compute", json_body=payload))
    assert limited.status_code == 429
    assert _body(limited)["error"]["code"] == "RATE_LIMITED"
    clock.advance(61)
    ok = routes.compute_match(_req("POST", "http://localhost/api/v1/matches/compute", json_body=payload))
    assert ok.status_code == 200


def test_explanation_omitted_when_explainer_fails(monkeypatch, store, queue, clock):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = MatchingService(
        store=store,
        queue=queue,
        embedder=HashEmbedder(),
        explainer=BoomExplainer(),
        clock=clock,
    )
    set_service(service)
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": HIGH_JOB, "explanation": True},
        )
    )
    set_service(None)
    get_settings.cache_clear()
    assert resp.status_code == 200
    body = _body(resp)
    assert "explanation" not in body
    assert "score" in body


def test_explanation_is_word_safe_and_capped(svc):
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": HIGH_JOB, "explanation": True, "threshold": 0},
        )
    )
    body = _body(resp)
    assert resp.status_code == 200
    assert body["explanation"]
    assert len(body["explanation"]) <= 500
    assert not body["explanation"].endswith(" ")


def test_async_compute_and_cancel(svc, queue):
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": HIGH_JOB, "mode": "async"},
        )
    )
    assert resp.status_code == 202
    operation_id = _body(resp)["operationId"]
    assert queue.of("match-compute")
    cancelled = routes.cancel_operation(
        _req(
            "POST",
            f"http://localhost/api/v1/operations/{operation_id}/cancel",
            route={"operationId": operation_id},
        )
    )
    assert cancelled.status_code == 200
    assert _body(cancelled)["cancelled"] is True
    svc.drain()
    status = _body(
        routes.get_operation(
            _req(
                "GET",
                f"http://localhost/api/v1/operations/{operation_id}",
                route={"operationId": operation_id},
            )
        )
    )
    assert status["status"] == "failed"
    listed = _body(routes.list_match_results(_req("GET", "http://localhost/api/v1/match-results")))
    assert listed["items"] == []


def test_poison_message_fails_pair(svc):
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": HIGH_JOB, "mode": "async"},
        )
    )
    operation_id = _body(resp)["operationId"]
    svc.process_compute({"operationId": operation_id, "index": 0}, dequeue_count=6)
    status = svc.get_operation(USER, operation_id)
    assert status["status"] == "failed"
    assert "poisoned" in (status.get("error") or "")


def test_text_loader_resolves_ids(svc, loader):
    loader.put_resume(USER, "r-1", RESUME)
    loader.put_job(USER, "j-1", HIGH_JOB)
    resp = routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeId": "r-1", "jobId": "j-1"},
        )
    )
    body = _body(resp)
    assert resp.status_code == 200
    assert body["persisted"] is True
    assert body["input"]["resumeId"] == "r-1"
    assert body["input"]["jobId"] == "j-1"


def test_keyword_title_outweighs_company():
    resume = "acme python"
    title_job = "Title: acme\nSkills: none\nCompany: other"
    company_job = "Title: other\nCompany: acme\nSkills: none"
    assert keyword_score(resume, title_job) > keyword_score(resume, company_job)


def test_cosine_identical_and_orthogonal():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

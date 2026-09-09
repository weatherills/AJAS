"""Learning Loop Database PRD — uniqueness, versioning, metrics freeze."""

from __future__ import annotations

import pytest

from app.learning.constants import DEFAULT_THRESHOLD, DEFAULT_WEIGHTS, GLOBAL_CONFIG_ID
from app.learning.errors import LearningNotFoundError, LearningValidationError
from app.learning.keys import utc_now
from app.learning.memory import InMemoryLearningStore
from app.learning.models import DecisionLog, Recommendation


def test_one_decision_per_recommendation_last_write_wins():
    store = InMemoryLearningStore(seed=False)
    now = utc_now()
    rec = store.upsert_recommendation(
        Recommendation(
            id="rec-1",
            user_id="u1",
            job_id="j1",
            score=0.8,
            weight_config_id=GLOBAL_CONFIG_ID,
            threshold=DEFAULT_THRESHOLD,
            generated_at=now,
            model_version="v1",
        )
    )
    first = store.put_decision(
        DecisionLog(
            user_id="u1",
            recommendation_id=rec.id,
            job_id="j1",
            decision="approve",
            score_at_decision=0.8,
            threshold_at_decision=0.7,
            model_version="v1",
            idempotency_key="a",
            created_at=now,
            updated_at=now,
        )
    )
    second = store.put_decision(
        DecisionLog(
            user_id="u1",
            recommendation_id=rec.id,
            job_id="j1",
            decision="reject",
            score_at_decision=0.8,
            threshold_at_decision=0.7,
            model_version="v1",
            idempotency_key="b",
            created_at=now,
            updated_at=now,
        )
    )
    assert second.id == first.id
    assert store.get_decision_by_rec("u1", rec.id).decision == "reject"
    assert len(store.list_decisions("u1")) == 1


def test_recommendation_snapshot_is_immutable():
    store = InMemoryLearningStore(seed=False)
    now = utc_now()
    store.upsert_recommendation(
        Recommendation(
            id="rec-2",
            user_id="u1",
            job_id="j1",
            score=0.5,
            score_components={"keyword": 0.4},
            weight_config_id=GLOBAL_CONFIG_ID,
            threshold=0.7,
            generated_at=now,
            model_version="v1",
        )
    )
    updated = store.upsert_recommendation(
        Recommendation(
            id="rec-2",
            user_id="u1",
            job_id="j1",
            score=0.99,
            score_components={"keyword": 0.9},
            weight_config_id="other",
            threshold=0.2,
            generated_at="2099-01-01T00:00:00Z",
            model_version="v9",
            status="decided",
        )
    )
    assert updated.score == 0.5
    assert updated.threshold == 0.7
    assert updated.weight_config_id == GLOBAL_CONFIG_ID
    assert updated.status == "decided"


def test_params_require_user_id():
    store = InMemoryLearningStore(seed=False)
    with pytest.raises(LearningValidationError):
        store.get_or_create_params(" ")


def test_missing_recommendation():
    store = InMemoryLearningStore(seed=False)
    with pytest.raises(LearningNotFoundError):
        store.get_recommendation("nope")


def test_demo_seed_has_enough_samples_for_window():
    store = InMemoryLearningStore(seed=False)
    store.seed_demo("u1")
    assert len(store.list_decisions("u1")) >= 20
    params = store.get_or_create_params("u1")
    assert params.weights["keyword"] == DEFAULT_WEIGHTS["keyword"]
    assert params.source == "global"

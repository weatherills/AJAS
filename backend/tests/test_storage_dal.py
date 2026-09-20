"""Cosmos DAL: CRUD, retries, RU logging, pagination."""

from __future__ import annotations

import pytest

from app.metrics import reset, snapshot
from app.storage.dal import CosmosDAL, with_retry
from app.storage.testing import FakeDatabase


class _Throttle(Exception):
    status_code = 429


def test_dal_crud_and_partitioned_pagination():
    reset()
    dal = CosmosDAL(FakeDatabase())
    created = dal.create("matches", {"id": "m1", "user_id": "u1", "status": "PENDING"})
    assert created["id"] == "m1"
    read = dal.read("matches", "m1", partition_key="u1")
    assert read["status"] == "PENDING"
    dal.upsert("matches", {"id": "m2", "user_id": "u1", "status": "PENDING"})
    dal.upsert("matches", {"id": "m3", "user_id": "u2", "status": "PENDING"})
    page = dal.query(
        "matches",
        "SELECT * FROM c",
        partition_key="u1",
        max_items=1,
    )
    assert len(page.items) == 1
    assert page.continuation
    page2 = dal.query(
        "matches",
        "SELECT * FROM c",
        partition_key="u1",
        continuation=page.continuation,
        max_items=1,
    )
    assert page2.items
    assert {row["id"] for row in page.items + page2.items} == {"m1", "m2"}
    dal.replace("matches", "m1", {"id": "m1", "user_id": "u1", "status": "APPROVED"})
    assert dal.read("matches", "m1", partition_key="u1")["status"] == "APPROVED"
    dal.delete("matches", "m1", partition_key="u1")
    with pytest.raises(KeyError):
        dal.read("matches", "m1", partition_key="u1")
    counters = snapshot()["counters"]
    assert counters["cosmos.ops"] >= 1
    assert counters["cosmos.ru"] >= 1


def test_retry_on_throttle_then_succeed():
    reset()
    hits = {"n": 0}

    def _flaky():
        hits["n"] += 1
        if hits["n"] < 3:
            raise _Throttle("throttled")
        return {"ok": True}

    assert with_retry(_flaky, retries=4, delay=0) == {"ok": True}
    assert hits["n"] == 3
    assert snapshot()["counters"]["cosmos.throttles"] == 2


def test_non_retryable_errors_surface():
    def _boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        with_retry(_boom, retries=4, delay=0)

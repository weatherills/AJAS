"""Synthetic DAL load that tracks RU against the daily budget SLO."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.metrics import reset as reset_metrics, snapshot as metrics_snapshot
from app.storage.dal import CosmosDAL
from app.storage.testing import FakeDatabase

HOT_PATHS = ("users.point", "matches.list", "resumes.list", "review.queue", "email.thread_messages")
P95_RU_PER_OP = 5.0


def run_load(*, iterations: int = 40, ru_budget: float | None = None) -> dict[str, Any]:
    reset_metrics()
    dal = CosmosDAL(FakeDatabase())
    stamp = "2026-01-15T12:00:00+00:00"
    dal.upsert("users", {"id": "u1", "email": "ada@ajas.dev", "created_at": stamp, "updated_at": stamp})
    for index in range(10):
        dal.upsert(
            "matches",
            {
                "id": f"m{index}",
                "user_id": "u1",
                "status": "PENDING",
                "queued_at": stamp,
                "job_title": "Eng",
            },
        )
        dal.upsert(
            "resumes",
            {"id": f"r{index}", "user_id": "u1", "original_filename": "cv.pdf", "created_at": stamp, "updated_at": stamp},
        )
    dal.upsert(
        "email_messages",
        {
            "id": "msg1",
            "email_account_id": "acct1",
            "email_thread_id": "th1",
            "from_address": "recruiter@acme.test",
            "body_text": "hello",
            "created_at": stamp,
        },
    )
    for _ in range(iterations):
        dal.read("users", "u1", partition_key="u1")
        dal.query("matches", "SELECT * FROM c", partition_key="u1", max_items=10)
        dal.query("resumes", "SELECT * FROM c", partition_key="u1", max_items=10)
        dal.query("matches", "SELECT * FROM c WHERE c.status = 'PENDING'", partition_key="u1", max_items=10)
        dal.query("email_messages", "SELECT * FROM c", partition_key="acct1", max_items=10)
    counters = metrics_snapshot()["counters"]
    ru = float(counters.get("cosmos.ru") or 0)
    ops = float(counters.get("cosmos.ops") or 0)
    budget = float(ru_budget if ru_budget is not None else get_settings().cosmos_daily_ru_budget or 0)
    per_op = ru / ops if ops else 0.0
    return {
        "schema": "ajas.cosmos.load.v1",
        "paths": list(HOT_PATHS),
        "iterations": iterations,
        "ops": ops,
        "ru": ru,
        "ruPerOp": per_op,
        "budget": budget,
        "ok": per_op <= P95_RU_PER_OP and (not budget or ru <= budget),
        "slo": f"hot paths ≤ {P95_RU_PER_OP} RU/op in FakeDatabase / emulator",
    }

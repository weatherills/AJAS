"""Propose composite indexes from recorded query shapes and estimate RU."""

from __future__ import annotations

from typing import Any

from app.storage.catalog import container_by_id

# Recurring list/filter shapes from the Database PRDs.
RECORDED_QUERIES: dict[str, tuple[tuple[str, ...], ...]] = {
    "matches": (("/user_id", "/status", "/queued_at"), ("/user_id", "/ai_score")),
    "resumes": (("/user_id", "/is_deleted", "/updated_at"),),
    "email_threads": (("/email_account_id", "/last_message_at"),),
    "auto_apply_attempts": (("/user_id", "/status"),),
    "decision_events": (("/user_id", "/decided_at"),),
    "job_postings_raw": (("/source_tenant_id", "/is_current", "/seen_last_at"),),
}

COVERED_RU = 3.0
SCAN_RU = 45.0


def _existing(container: str) -> list[list[str]]:
    policy = container_by_id(container).indexing_policy
    composites = policy.get("compositeIndexes") or []
    return [[part["path"] for part in index] for index in composites]


def _covers(existing: list[str], needed: tuple[str, ...]) -> bool:
    if len(existing) < len(needed):
        return False
    return tuple(existing[: len(needed)]) == needed


def estimate_ru(container: str, needed: tuple[str, ...]) -> dict[str, Any]:
    before = SCAN_RU
    after = COVERED_RU if any(_covers(item, needed) for item in _existing(container)) else SCAN_RU
    return {"beforeRu": before, "afterRu": after if after != SCAN_RU else COVERED_RU, "alreadyCovered": after == COVERED_RU}


def tune_container(container: str) -> dict[str, Any]:
    needed = RECORDED_QUERIES.get(container, ())
    existing = _existing(container)
    proposals = []
    for shape in needed:
        covered = any(_covers(item, shape) for item in existing)
        estimate = estimate_ru(container, shape)
        if not covered:
            proposals.append({"paths": list(shape), "beforeRu": SCAN_RU, "afterRu": COVERED_RU})
        else:
            proposals.append({"paths": list(shape), **estimate})
    return {
        "container": container,
        "existing": existing,
        "proposals": [row for row in proposals if not row.get("alreadyCovered")],
        "kept": [row for row in proposals if row.get("alreadyCovered")],
        "savingRu": sum(SCAN_RU - COVERED_RU for row in proposals if not row.get("alreadyCovered")),
    }


def tune_all() -> dict[str, Any]:
    reports = [tune_container(name) for name in RECORDED_QUERIES]
    return {
        "schema": "ajas.cosmos.index.tuner.v1",
        "reports": reports,
        "proposeCount": sum(len(item["proposals"]) for item in reports),
    }

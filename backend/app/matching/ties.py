"""Deterministic tie-breakers when match scores collide."""

from __future__ import annotations

from typing import Any


def tie_key(row: dict[str, Any]) -> tuple:
    score = -float(row.get("score") or row.get("fair_score") or 0.0)
    posted = str(row.get("posted_at") or row.get("postedAt") or "")
    source = str(row.get("source_type") or row.get("source") or "")
    job_id = str(row.get("id") or row.get("source_posting_id") or "")
    posted_rank = tuple(-ord(char) for char in posted)
    return (score, posted_rank, source, job_id)


def sort_with_ties(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=tie_key)

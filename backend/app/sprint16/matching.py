"""Sprint 16 matching, ranking, and explanation helpers."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.sprint15.matching import (
    confidence,
    counterfactual_s15,
    delta_checksum,
    fit_label,
    listwise_v2,
    location_boost,
    recency_s15,
    title_family,
)


_LAG: list[dict[str, Any]] = []


def reset() -> None:
    _LAG.clear()


def content_hash_skip(doc_id: str, text: str, seen: dict[str, str]) -> dict[str, Any]:
    row = delta_checksum(doc_id, text, seen)
    digest = hashlib.sha256((text or "").encode()).hexdigest()[:16]
    return {**row, "schema": "ajas.hash.v2", "digest": digest}


def replica_probe(*, replica_ms: float, primary_ms: float, max_ms: float = 250) -> dict[str, Any]:
    lag = abs(replica_ms - primary_ms)
    row = {"lagMs": lag, "healthy": lag <= max_ms, "probe": True}
    _LAG.append(row)
    return row


def commute_proxy(*, km: float, kmh: float = 40) -> dict[str, Any]:
    minutes = 0.0 if km <= 0 else (km / max(kmh, 1)) * 60
    boost = location_boost(km=km)
    return {"minutes": round(minutes, 1), "boost": boost}


def title_family_v2(title: str) -> str:
    family = title_family(title)
    lowered = (title or "").lower()
    if "product" in lowered:
        return "product"
    if "design" in lowered or "ux" in lowered:
        return "design"
    return family


def equity_overlap(resume_pct: float, job_pct: float, *, band: float = 0.02) -> dict[str, Any]:
    hit = abs(resume_pct - job_pct) <= band or (resume_pct > 0 and job_pct > 0 and min(resume_pct, job_pct) > 0)
    return {"hit": hit, "resume": resume_pct, "job": job_pct}


def listwise_v3(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = listwise_v2(jobs)
    return [{**row, "schema": "ajas.ltr.v3"} for row in ranked]


def thompson(*, alpha: float, beta: float, draw: float) -> str:
    mean = alpha / max(alpha + beta, 0.0001)
    return "explore" if draw > mean else "exploit"


def why_this_not_that(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_score = float(left.get("score") or 0)
    right_score = float(right.get("score") or 0)
    winner = "left" if left_score >= right_score else "right"
    return {"winner": winner, "delta": abs(left_score - right_score), "left": left, "right": right}


def prediction_interval(*, keyword: float, semantic: float, recency: float) -> dict[str, Any]:
    row = confidence(keyword=keyword, semantic=semantic, recency=recency)
    return {**row, "schema": "ajas.fit.pi"}


def debias_company(name: str) -> str:
    return re.sub(r"(?i)\b(inc|llc|ltd|corp|co)\b\.?", "", name or "").strip(" ,")


def recency_s16(*, months_ago: float) -> float:
    return recency_s15(months_ago=months_ago)


def counterfactual_s16(have: list[str], need: list[str]) -> dict[str, Any]:
    return counterfactual_s15(have, need)


def fit_s16(score: float) -> str:
    return fit_label(score)

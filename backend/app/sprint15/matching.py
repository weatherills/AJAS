"""Sprint 15 matching, ranking, and explanation helpers."""

from __future__ import annotations

import hashlib
from typing import Any

from app.sprint13.matching import fit_bucket
from app.sprint14.matching import counterfactual, missing_must_haves, recency_v2, sub_scores

_LAG: list[dict[str, Any]] = []


def reset() -> None:
    _LAG.clear()


def delta_checksum(doc_id: str, text: str, seen: dict[str, str]) -> dict[str, Any]:
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    skip = seen.get(doc_id) == digest
    seen[doc_id] = digest
    return {"id": doc_id, "checksum": digest, "skip": skip}


def replica_lag(*, replica_ms: float, primary_ms: float, max_ms: float = 250) -> dict[str, Any]:
    lag = abs(replica_ms - primary_ms)
    row = {"lagMs": lag, "healthy": lag <= max_ms}
    _LAG.append(row)
    return row


def location_boost(*, km: float, cap_km: float = 50) -> float:
    if km <= 0:
        return 1.0
    return max(0.0, 1.0 - min(km, cap_km) / cap_km)


def title_family(title: str) -> str:
    lowered = (title or "").lower()
    if "manager" in lowered or "director" in lowered:
        return "mgmt"
    if "data" in lowered:
        return "data"
    if "security" in lowered:
        return "security"
    return "eng"


def comp_overlap(resume_min: float, resume_max: float, job_min: float, job_max: float) -> dict[str, Any]:
    lo = max(resume_min, job_min)
    hi = min(resume_max, job_max)
    return {"overlap": max(0.0, hi - lo), "hit": hi > lo}


def listwise_v2(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(jobs, key=lambda row: float(row.get("score") or 0), reverse=True)
    return [{**row, "rank": i + 1} for i, row in enumerate(ranked)]


def epsilon_explore(*, score: float, epsilon: float = 0.1, draw: float) -> str:
    return "explore" if draw < epsilon else ("exploit" if score >= 0.5 else "explore")


def why_not(have: list[str], need: list[str]) -> dict[str, Any]:
    missing = missing_must_haves(have, need)
    return {"missing": missing, "reason": f"Missing {', '.join(missing) or 'nothing'}"}


def confidence(*, keyword: float, semantic: float, recency: float) -> dict[str, Any]:
    row = sub_scores(keyword=keyword, semantic=semantic, recency=recency)
    spread = max(keyword, semantic, recency) - min(keyword, semantic, recency)
    return {**row, "interval": round(max(0.0, 1 - spread), 3)}


def debias_title(title: str) -> str:
    cleaned = re_sub(title)
    return cleaned


def re_sub(title: str) -> str:
    import re

    return re.sub(r"(?i)\b(ninja|rockstar|guru|hacker)\b", "", title or "").strip()


def recency_s15(*, months_ago: float) -> float:
    return recency_v2(months_ago=months_ago)


def counterfactual_s15(have: list[str], need: list[str]) -> dict[str, Any]:
    return counterfactual(have, need)


def fit_label(score: float) -> str:
    return fit_bucket(score)

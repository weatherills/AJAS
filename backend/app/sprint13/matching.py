"""LTR logging, fit AB, explanations, collapse, boosts, visa, seniority, HNSW, shards, taxonomy."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.matching.keys import utc_now
from app.sprint12.security import redact_pii

_LTR: list[dict[str, Any]] = []
_TAXONOMY: dict[str, int] = defaultdict(int)
_REVIEW: list[dict[str, Any]] = []


def reset() -> None:
    _LTR.clear()
    _TAXONOMY.clear()
    _REVIEW.clear()


def ltr_log(*, user_id: str, job_id: str, features: dict[str, float], label: int | None = None) -> dict[str, Any]:
    row = {
        "schema": "ajas.ltr.v2",
        "userId": redact_pii(user_id, context="log"),
        "jobId": job_id,
        "features": dict(features),
        "label": label,
        "at": utc_now(),
    }
    _LTR.append(row)
    return row


def fit_bucket(score: float, *, variant: str = "control") -> str:
    if variant == "treatment":
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        return "C"
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    return "C"


def group_evidence(items: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {"skill": [], "domain": [], "other": []}
    for item in items:
        low = item.lower()
        if any(tok in low for tok in ("python", "azure", "react", "sql", "go")):
            groups["skill"].append(item)
        elif any(tok in low for tok in ("fintech", "health", "climate", "saas")):
            groups["domain"].append(item)
        else:
            groups["other"].append(item)
    return groups


def collapse_company(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in jobs:
        key = (job.get("company") or "").strip().lower()
        buckets[key].append(job)
    out = []
    for company, rows in buckets.items():
        top = sorted(rows, key=lambda row: float(row.get("score") or 0), reverse=True)[0]
        out.append({**top, "rollupCount": len(rows), "companyKey": company})
    return out


def recent_role_boost(*, months_ago: float, base: float = 1.0) -> float:
    if months_ago <= 12:
        return round(base * 1.15, 4)
    if months_ago <= 36:
        return round(base * (1.15 - (months_ago - 12) * 0.006), 4)
    return round(base * 0.9, 4)


def visa_rule(country: str, *, authorized: bool) -> dict[str, Any]:
    host = (country or "US").upper()
    needs = host in {"US", "GB", "CA", "AU", "DE"}
    return {"country": host, "authorized": authorized, "boost": 1.0 if authorized or not needs else 0.85, "gate": needs and not authorized}


def seniority_calibrate(title: str) -> dict[str, Any]:
    low = (title or "").lower()
    ladder = [("principal", 5), ("staff", 4), ("senior", 3), ("lead", 3), ("junior", 1), ("intern", 0)]
    level = 2
    label = "mid"
    for name, num in ladder:
        if name in low:
            level, label = num, name
            break
    return {"title": title, "level": level, "label": label}


def hnsw_tune(*, m: int = 16, ef: int = 64) -> dict[str, Any]:
    recall = min(0.99, 0.82 + m / 200 + ef / 800)
    latency_ms = 8 + m * 0.4 + ef * 0.05
    return {"m": m, "ef": ef, "recall": round(recall, 4), "latencyMs": round(latency_ms, 2)}


def shard_reindex(*, shards: int, backlog: int, max_inflight: int = 100) -> dict[str, Any]:
    inflight = min(backlog, max_inflight)
    return {"shards": shards, "inflight": inflight, "backpressure": backlog > max_inflight, "dropped": max(0, backlog - max_inflight)}


def observe_skill(name: str, *, count: int = 1) -> None:
    _TAXONOMY[name.strip().lower()] += int(count)


def taxonomy_extend(*, min_count: int = 3) -> dict[str, Any]:
    auto = [name for name, n in _TAXONOMY.items() if n >= min_count]
    for name in auto:
        _REVIEW.append({"skill": name, "status": "pending"})
    return {"proposed": auto, "queue": list(_REVIEW)}

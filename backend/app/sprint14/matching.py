"""Sprint 14 matching, ranking, and explanation helpers."""

from __future__ import annotations

from typing import Any

from app.matching.reindex import ReindexSweeper
from app.matching.vectors import VectorStore
from app.resumes.multilingual import detect_lang
from app.sprint12.security import redact_pii
from app.sprint13.matching import collapse_company, fit_bucket, ltr_log, recent_role_boost, shard_reindex

_STORE = VectorStore()
_SWEEP: ReindexSweeper | None = None
_CAL: list[dict[str, Any]] = []


def reset() -> None:
    global _SWEEP
    _STORE.live.clear()
    _STORE.tombstones.clear()
    _SWEEP = None
    _CAL.clear()


def reindex_sweep(docs: list[tuple[str, str]]) -> dict[str, Any]:
    global _SWEEP
    _SWEEP = ReindexSweeper(embed=lambda texts: [[float(len(t)), 1.0] for t in texts])
    for doc_id, text in docs:
        _SWEEP.enqueue(doc_id, text)
    return _SWEEP.sweep()


def vacuum_v2() -> dict[str, Any]:
    _STORE.upsert("a", [1.0])
    _STORE.delete("a")
    _STORE.upsert("b", [2.0])
    return {"schema": "ajas.vector.vacuum.v2", **_STORE.vacuum()}


def recency_v2(*, months_ago: float) -> float:
    return recent_role_boost(months_ago=months_ago)


def dedupe_v2(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return collapse_company(jobs)


def multilingual_jd(text: str) -> dict[str, Any]:
    lang = detect_lang(text)
    return {"lang": lang, "translate": lang != "en", "branch": f"jd.{lang}"}


def ltr_event(*, user_id: str, job_id: str, event: str) -> dict[str, Any]:
    label = {"click": 1, "open": 1, "reply": 2}.get(event, 0)
    row = ltr_log(user_id=user_id, job_id=job_id, features={"event": 1.0}, label=label)
    return {**row, "event": event}


def pairwise_rows(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(jobs, key=lambda row: float(row.get("score") or 0), reverse=True)
    out = []
    for left, right in zip(ranked, ranked[1:]):
        out.append({"chosen": left["id"], "rejected": right["id"]})
    return out


def calibration_monitor(scores: list[float]) -> dict[str, Any]:
    buckets = [fit_bucket(score) for score in scores]
    row = {"n": len(scores), "A": buckets.count("A"), "B": buckets.count("B"), "C": buckets.count("C")}
    _CAL.append(row)
    return row


def counterfactual(have: list[str], need: list[str]) -> dict[str, Any]:
    missing = [item for item in need if item.lower() not in {h.lower() for h in have}]
    return {"add": missing, "suggestion": f"Add {', '.join(missing) or 'no extra skills'}"}


def missing_must_haves(resume: list[str], required: list[str]) -> list[str]:
    have = {item.lower() for item in resume}
    return [item for item in required if item.lower() not in have]


def sub_scores(*, keyword: float, semantic: float, recency: float) -> dict[str, Any]:
    total = round(0.5 * keyword + 0.4 * semantic + 0.1 * recency, 3)
    return {"keyword": keyword, "semantic": semantic, "recency": recency, "total": total, "bucket": fit_bucket(total * 100)}


def shard_backpressure(*, shards: int, backlog: int) -> dict[str, Any]:
    return shard_reindex(shards=shards, backlog=backlog)

"""Match feedback, ranking v3 feature store, AB tests, and skill graph."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from typing import Any
from uuid import uuid4

from app.matching.keys import utc_now

_FEEDBACK: dict[str, dict[str, Any]] = {}
_WEIGHTS: dict[str, dict[str, float]] = {}
_FEATURES: list[dict[str, Any]] = []
_AB: dict[str, dict[str, Any]] = {}
_ASSIGN: dict[tuple[str, str], str] = {}
_GRAPH: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def reset() -> None:
    _FEEDBACK.clear()
    _WEIGHTS.clear()
    _FEATURES.clear()
    _AB.clear()
    _ASSIGN.clear()
    _GRAPH.clear()


def record_feedback(*, user_id: str, job_id: str, vote: str, reason: str | None = None) -> dict[str, Any]:
    if vote not in {"up", "down"}:
        raise ValueError("vote must be up or down")
    key = f"{user_id}:{job_id}"
    row = {
        "id": str(uuid4()),
        "userId": user_id,
        "jobId": job_id,
        "vote": vote,
        "reason": (reason or "").strip()[:240] or None,
        "at": utc_now(),
    }
    _FEEDBACK[key] = row
    delta = 0.05 if vote == "up" else -0.05
    weights = _WEIGHTS.setdefault(user_id, {"keyword": 0.4, "semantic": 0.6})
    weights["semantic"] = min(0.85, max(0.15, round(weights["semantic"] + delta, 4)))
    weights["keyword"] = round(1.0 - weights["semantic"], 4)
    return row


def weights_for(user_id: str) -> dict[str, float]:
    return dict(_WEIGHTS.get(user_id) or {"keyword": 0.4, "semantic": 0.6})


def log_feature_row(*, user_id: str, job_id: str, features: dict[str, float], label: int | None = None) -> dict[str, Any]:
    row = {
        "userId": user_id,
        "jobId": job_id,
        "features": dict(features),
        "label": label,
        "at": utc_now(),
    }
    _FEATURES.append(row)
    return row


def train_offline(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = rows if rows is not None else [r for r in _FEATURES if r.get("label") is not None]
    if len(data) < 4:
        return {"status": "skipped", "reason": "need_4_labeled_rows", "n": len(data)}
    pos = [r for r in data if r["label"] == 1]
    neg = [r for r in data if r["label"] == 0]
    keys = sorted({k for r in data for k in r["features"]})

    def mean(subset: list[dict[str, Any]], key: str) -> float:
        if not subset:
            return 0.0
        return sum(float(r["features"].get(key) or 0) for r in subset) / len(subset)

    weights = {key: round(mean(pos, key) - mean(neg, key), 4) for key in keys}
    return {"status": "fitted", "n": len(data), "weights": weights, "positive": len(pos), "negative": len(neg)}


def upsert_experiment(key: str, variants: list[str], *, traffic: float = 1.0) -> dict[str, Any]:
    if len(variants) < 2:
        raise ValueError("need two variants")
    row = {"key": key, "variants": list(variants), "traffic": float(traffic), "metrics": {v: {"n": 0, "reward": 0.0} for v in variants}}
    _AB[key] = row
    return row


def assign_variant(experiment: str, user_id: str) -> str:
    cfg = _AB[experiment]
    digest = hashlib.sha256(f"{experiment}:{user_id}".encode()).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    if bucket > cfg["traffic"]:
        return cfg["variants"][0]
    idx = int(digest[8:16], 16) % len(cfg["variants"])
    variant = cfg["variants"][idx]
    _ASSIGN[(experiment, user_id)] = variant
    return variant


def track_metric(experiment: str, variant: str, reward: float = 1.0) -> dict[str, Any]:
    cell = _AB[experiment]["metrics"][variant]
    cell["n"] += 1
    cell["reward"] += float(reward)
    return dict(cell)


def explanation_style(user_id: str) -> str:
    if "explain.style" not in _AB:
        upsert_experiment("explain.style", ["bullet", "narrative"])
    return assign_variant("explain.style", user_id)


def format_explanation(style: str, bullets: list[str]) -> str:
    clean = [b.strip() for b in bullets if b and b.strip()]
    if style == "narrative":
        if not clean:
            return ""
        if len(clean) == 1:
            return clean[0]
        return "; ".join(clean[:-1]) + "; and " + clean[-1]
    return "\n".join(f"• {item}" for item in clean)


def observe_skills(skills: list[str]) -> None:
    names = sorted({s.strip().lower() for s in skills if s and s.strip()})
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            _GRAPH[left][right] += 1
            _GRAPH[right][left] += 1


def expand_synonyms(skill: str, *, min_count: int = 2) -> list[str]:
    key = skill.strip().lower()
    neighbors = [(name, count) for name, count in _GRAPH.get(key, {}).items() if count >= min_count]
    neighbors.sort(key=lambda item: (-item[1], item[0]))
    return [name for name, _ in neighbors[:8]]


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))

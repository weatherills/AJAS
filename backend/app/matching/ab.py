"""Stable A/B assignment for keyword vs semantic scoring weights."""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict

VARIANTS: dict[str, tuple[float, float]] = {
    "kw30": (0.3, 0.7),
    "balanced": (0.5, 0.5),
}

_METRICS: dict[str, dict[str, int]] = defaultdict(lambda: {"shown": 0, "approved": 0})


def ab_enabled() -> bool:
    raw = os.getenv("MATCH_AB_TEST", "")
    if raw:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    try:
        from app.config import get_settings

        return bool(get_settings().match_ab_test)
    except Exception:
        return False


def assign_variant(user_id: str) -> str:
    digest = hashlib.sha256((user_id or "anon").encode("utf-8")).hexdigest()
    return "kw30" if int(digest[:8], 16) % 2 == 0 else "balanced"


def weights_for(user_id: str, keyword_weight: float, semantic_weight: float) -> tuple[float, float, str]:
    if not ab_enabled():
        return keyword_weight, semantic_weight, "control"
    name = assign_variant(user_id)
    keyword, semantic = VARIANTS[name]
    return keyword, semantic, name


def record(bucket: str, *, approved: bool = False) -> dict[str, int]:
    row = _METRICS[bucket]
    row["shown"] += 1
    if approved:
        row["approved"] += 1
    return dict(row)


def snapshot() -> dict[str, dict[str, float | int]]:
    out: dict[str, dict[str, float | int]] = {}
    for bucket, row in _METRICS.items():
        shown = row["shown"]
        out[bucket] = {
            "shown": shown,
            "approved": row["approved"],
            "precision": round(row["approved"] / shown, 3) if shown else 0.0,
        }
    return out


def reset_metrics() -> None:
    _METRICS.clear()

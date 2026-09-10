"""Stable A/B assignment for keyword vs semantic scoring weights."""

from __future__ import annotations

import hashlib
import os

VARIANTS: dict[str, tuple[float, float]] = {
    "kw30": (0.3, 0.7),
    "balanced": (0.5, 0.5),
}


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

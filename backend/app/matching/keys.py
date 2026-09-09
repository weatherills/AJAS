"""Score formula, hashes, and timestamps for Matching."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from app.matching.constants import DEFAULT_KEYWORD_WEIGHT, DEFAULT_SEMANTIC_WEIGHT, RETENTION_DAYS


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_ts(value: str):
    stamp = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def is_expired(completed_at: str | None, *, now: str | None = None) -> bool:
    if not completed_at:
        return False
    cutoff = parse_ts(now or utc_now()) - timedelta(days=RETENTION_DAYS)
    return parse_ts(completed_at) < cutoff


def clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def overall_score_pct(
    keyword_norm: float,
    semantic_norm: float,
    *,
    keyword_weight: float = DEFAULT_KEYWORD_WEIGHT,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
) -> int:
    raw = 100.0 * (keyword_weight * clamp_unit(keyword_norm) + semantic_weight * clamp_unit(semantic_norm))
    return int(round(max(0.0, min(100.0, raw))))


def idempotency_key(
    *,
    user_id: str,
    resume_ref: str,
    job_ref: str,
    model_version_id: str,
    threshold_used: int,
) -> str:
    payload = f"{user_id}|{resume_ref}|{job_ref}|{model_version_id}|{threshold_used}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

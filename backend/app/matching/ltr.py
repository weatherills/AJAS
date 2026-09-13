"""Learning-to-rank scaffolding: log match features without training a model."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.mail.pii import redact_pii

log = logging.getLogger("ajas")

FEATURE_KEYS = (
    "keyword",
    "semantic",
    "location_boost",
    "seniority_boost",
    "visa_boost",
    "must_have_coverage",
    "required_count",
    "title_overlap",
)


def feature_vector(
    *,
    keyword: float,
    semantic: float,
    location_boost: float,
    seniority_boost: float,
    visa_boost: float,
    must_have_coverage: float,
    required_count: int,
    title_overlap: int,
) -> dict[str, float]:
    return {
        "keyword": round(float(keyword), 4),
        "semantic": round(float(semantic), 4),
        "location_boost": round(float(location_boost), 4),
        "seniority_boost": round(float(seniority_boost), 4),
        "visa_boost": round(float(visa_boost), 4),
        "must_have_coverage": round(float(must_have_coverage), 4),
        "required_count": float(required_count),
        "title_overlap": float(title_overlap),
    }


def log_features(user_id: str, job_id: str | None, features: dict[str, Any], score: float) -> None:
    payload = {
        "user_id": user_id,
        "job_id": job_id,
        "score": score,
        "features": features,
    }
    log.info("ajas.match.ltr %s", redact_pii(json.dumps(payload, default=str)))

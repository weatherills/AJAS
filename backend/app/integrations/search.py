"""Search inputs, result limits, and refresh cadence for extra job boards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EXPERIENCE_LEVELS = frozenset(
    {"internship", "entry", "associate", "mid", "senior", "staff", "director", "executive"}
)
WORKPLACES = frozenset({"remote", "hybrid", "onsite", "any"})
DEFAULT_LIMIT = 25
MAX_LIMIT = 100
DEFAULT_CADENCE_SECONDS = 3600
MIN_CADENCE_SECONDS = 300


@dataclass(frozen=True)
class SearchSpec:
    keywords: str = ""
    locations: tuple[str, ...] = ()
    experience: str | None = None
    workplace: str = "any"
    limit: int = DEFAULT_LIMIT
    cadence_seconds: int = DEFAULT_CADENCE_SECONDS

    def as_dict(self) -> dict[str, Any]:
        return {
            "keywords": self.keywords,
            "locations": list(self.locations),
            "experience": self.experience,
            "workplace": self.workplace,
            "limit": self.limit,
            "cadenceSeconds": self.cadence_seconds,
        }


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return [part for part in parts if part]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def parse_search(payload: Any | None = None) -> SearchSpec:
    raw = payload if isinstance(payload, dict) else {}
    keywords = str(raw.get("keywords") or raw.get("q") or "").strip()
    locations = tuple(_as_list(raw.get("locations") or raw.get("location")))
    experience = str(raw.get("experience") or raw.get("experienceLevel") or "").strip().lower() or None
    if experience and experience not in EXPERIENCE_LEVELS:
        experience = None
    workplace = str(raw.get("workplace") or raw.get("remote") or "any").strip().lower()
    if workplace in {"true", "1", "yes"}:
        workplace = "remote"
    if workplace not in WORKPLACES:
        workplace = "any"
    try:
        limit = int(raw.get("limit") or raw.get("resultLimit") or DEFAULT_LIMIT)
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    limit = max(1, min(MAX_LIMIT, limit))
    try:
        cadence = int(raw.get("cadenceSeconds") or raw.get("refreshCadence") or DEFAULT_CADENCE_SECONDS)
    except (TypeError, ValueError):
        cadence = DEFAULT_CADENCE_SECONDS
    cadence = max(MIN_CADENCE_SECONDS, cadence)
    return SearchSpec(
        keywords=keywords,
        locations=locations,
        experience=experience,
        workplace=workplace,
        limit=limit,
        cadence_seconds=cadence,
    )


def matches_search(job: dict[str, Any], spec: SearchSpec) -> bool:
    hay = " ".join(
        str(job.get(key) or "")
        for key in ("title", "company", "location", "description", "body", "seniority", "workplace")
    ).lower()
    if spec.keywords:
        tokens = [tok for tok in spec.keywords.lower().split() if tok]
        if tokens and not all(tok in hay for tok in tokens):
            return False
    if spec.locations:
        loc = str(job.get("location") or "").lower()
        if not any(item.lower() in loc or item.lower() in hay for item in spec.locations):
            return False
    if spec.experience:
        seniority = str(job.get("seniority") or job.get("experience") or "").lower()
        if spec.experience not in seniority and spec.experience not in hay:
            return False
    if spec.workplace and spec.workplace != "any":
        workplace = str(job.get("workplace") or "").lower()
        if spec.workplace not in workplace and spec.workplace not in hay:
            return False
    return True


SUPPORTED_INPUTS = {
    "keywords": "Free-text title/skill query (space-separated AND).",
    "locations": "City, region, or country strings; comma-separated or list.",
    "experience": sorted(EXPERIENCE_LEVELS),
    "workplace": sorted(WORKPLACES),
    "limit": {"min": 1, "max": MAX_LIMIT, "default": DEFAULT_LIMIT},
    "cadenceSeconds": {"min": MIN_CADENCE_SECONDS, "default": DEFAULT_CADENCE_SECONDS},
}

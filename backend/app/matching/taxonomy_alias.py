"""Deprecate outdated skill terms by aliasing them to a canonical skill."""

from __future__ import annotations

from app.matching.taxonomy import SKILL_SYNONYMS, canonical_skill

DEPRECATED = {
    "angularjs": "javascript",
    "backbone": "javascript",
    "bower": "npm",
    "mesos": "kubernetes",
}


def resolve(term: str) -> dict[str, str | bool]:
    raw = (term or "").strip().lower()
    if raw in DEPRECATED:
        return {"term": raw, "canonical": DEPRECATED[raw], "deprecated": True}
    return {"term": raw, "canonical": canonical_skill(raw), "deprecated": False}


def apply_deprecations() -> int:
    for old, new in DEPRECATED.items():
        aliases = list(SKILL_SYNONYMS.get(new, ()))
        if old not in aliases:
            aliases.append(old)
            SKILL_SYNONYMS[new] = tuple(aliases)
    return len(DEPRECATED)

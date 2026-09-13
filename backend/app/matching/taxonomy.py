"""Skills taxonomy: synonyms and weightings used by matching and CLI rebuilds."""

from __future__ import annotations

from typing import Iterable

# Seeded from Matching / Resume PRDs plus common engineering aliases.
SKILL_SYNONYMS: dict[str, tuple[str, ...]] = {
    "python": ("py", "python3", "cpython"),
    "javascript": ("js", "ecmascript", "node", "nodejs"),
    "typescript": ("ts",),
    "kubernetes": ("k8s", "kube"),
    "postgresql": ("postgres", "psql"),
    "amazon": ("aws", "amazon web services"),
    "azure": ("microsoft azure", "az"),
    "gcp": ("google cloud", "gcloud"),
    "react": ("reactjs", "react.js"),
    "cicd": ("ci/cd", "continuous integration"),
    "machinelearning": ("ml", "machine learning"),
    "naturallanguage": ("nlp", "natural language"),
}

SKILL_WEIGHTS: dict[str, float] = {
    "python": 1.2,
    "kubernetes": 1.15,
    "azure": 1.1,
    "typescript": 1.05,
    "react": 1.0,
}


def canonical_skill(token: str) -> str:
    raw = (token or "").strip().lower().replace(" ", "").replace("-", "")
    if not raw:
        return ""
    for canonical, aliases in SKILL_SYNONYMS.items():
        if raw == canonical or raw in {alias.replace(" ", "").replace("-", "") for alias in aliases}:
            return canonical
    return raw


def expand_terms(terms: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for term in terms:
        canon = canonical_skill(term)
        if not canon:
            continue
        out.add(canon)
        out.add(term.lower())
        aliases = SKILL_SYNONYMS.get(canon, ())
        out.update(alias.replace(" ", "") for alias in aliases)
    return out


def skill_weight(token: str) -> float:
    return SKILL_WEIGHTS.get(canonical_skill(token), 1.0)


def rebuild_taxonomy() -> dict[str, object]:
    """CLI helper: return the current seed so operators can dump/rebuild."""
    return {
        "synonyms": {key: list(value) for key, value in SKILL_SYNONYMS.items()},
        "weights": dict(SKILL_WEIGHTS),
        "version": "taxonomy-s9-v1",
    }

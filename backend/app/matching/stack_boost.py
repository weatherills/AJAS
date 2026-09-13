"""Preferred tech-stack boosts aligned with AJAS PRD defaults."""

from __future__ import annotations

from app.matching.scoring import tokenize

PRD_STACK = {
    "python": 4.0,
    "typescript": 3.5,
    "react": 3.0,
    "azure": 3.0,
    "cosmos": 2.0,
    "openai": 2.0,
}


def stack_boost(resume_text: str, job_text: str, *, weights: dict[str, float] | None = None) -> dict[str, object]:
    table = weights or PRD_STACK
    resume = set(tokenize(resume_text))
    job = set(tokenize(job_text))
    hits = []
    total = 0.0
    for term, weight in table.items():
        if term in resume and term in job:
            hits.append(term)
            total += weight
    return {"boost": round(total, 2), "hits": hits, "stack": sorted(table)}

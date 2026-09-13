"""Pick resume highlights that overlap the job posting."""

from __future__ import annotations

from app.matching.scoring import tokenize
from app.resumes.achievements import classify_bullet


def select_highlights(bullets: list[str], job_text: str, *, limit: int = 3) -> list[dict[str, str]]:
    job_terms = set(tokenize(job_text))
    scored = []
    for bullet in bullets:
        overlap = len(set(tokenize(bullet)) & job_terms)
        kind = classify_bullet(bullet)
        bonus = 1 if kind == "achievement" else 0
        scored.append((overlap + bonus, bullet, kind))
    scored.sort(reverse=True)
    return [{"text": text, "kind": kind} for _, text, kind in scored[:limit]]

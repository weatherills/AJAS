"""Score project/impact bullets extracted from resume text."""

from __future__ import annotations

import re

_BULLET = re.compile(r"^(?:[\-\*•–]|\d+[.)])\s+")
_PROJECT_HEAD = re.compile(r"(?i)^(projects?|selected projects|impact)\s*:?\s*$")
_NUMBER = re.compile(r"(?i)(\d+(?:\.\d+)?)\s*(%|percent|x|k|m|million|billion)?")
_VERBS = re.compile(
    r"(?i)\b(increased|reduced|cut|grew|launched|shipped|saved|improved|migrated|automated|led|owned)\b"
)


def extract_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    in_projects = False
    for raw in (text or "").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if _PROJECT_HEAD.match(stripped):
            in_projects = True
            continue
        if _BULLET.match(stripped) or in_projects:
            cleaned = _BULLET.sub("", stripped).strip() if _BULLET.match(stripped) else stripped
            if cleaned:
                bullets.append(cleaned)
            if in_projects and not _BULLET.match(stripped) and stripped.endswith(":"):
                continue
        if stripped.lower().startswith("experience:") or stripped.lower().startswith("education:"):
            in_projects = False
    return bullets


def score_bullet(text: str) -> dict[str, object]:
    numbers = _NUMBER.findall(text or "")
    verb = bool(_VERBS.search(text or ""))
    score = 0
    if verb:
        score += 40
    if numbers:
        score += min(40, 15 * len(numbers))
    if "%" in (text or "") or "percent" in (text or "").lower():
        score += 20
    return {
        "text": text,
        "score": min(100, score),
        "hasImpactVerb": verb,
        "metrics": ["".join(part for part in hit if part) for hit in numbers],
    }


def extract_and_score(text: str) -> dict[str, object]:
    bullets = extract_bullets(text)
    scored = [score_bullet(item) for item in bullets]
    scored.sort(key=lambda row: int(row["score"]), reverse=True)
    return {
        "bullets": scored,
        "top": scored[:5],
        "impactScore": round(sum(int(row["score"]) for row in scored) / len(scored), 1) if scored else 0.0,
    }

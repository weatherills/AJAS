"""Top evidence sentences that justify a match score."""

from __future__ import annotations

import re

from app.matching.scoring import tokenize
from app.matching.taxonomy import expand_terms

_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def _sentences(text: str) -> list[str]:
    parts = [re.sub(r"\s+", " ", part).strip(" -•\t") for part in _SENTENCE.split(text or "")]
    return [part for part in parts if len(part) >= 24]


def evidence_sentences(resume_text: str, job_text: str, *, limit: int = 5) -> list[str]:
    """Return up to ``limit`` job sentences with the strongest resume overlap."""
    resume_terms = expand_terms(tokenize(resume_text))
    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(_sentences(job_text)):
        job_terms = expand_terms(tokenize(sentence))
        overlap = len(resume_terms & job_terms)
        if overlap <= 0:
            continue
        scored.append((overlap, -index, sentence))
    scored.sort(reverse=True)
    seen: set[str] = set()
    out: list[str] = []
    for _overlap, _order, sentence in scored:
        key = sentence.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(sentence[:280])
        if len(out) >= limit:
            break
    return out

"""Explanation summaries for a match score."""

from __future__ import annotations

import re
from typing import Protocol

from app.matching.scoring import parse_job_fields, tokenize, truncate_words

_EMAIL = re.compile(r"\b\S+@\S+\.\S+\b")


class Explainer(Protocol):
    def explain(
        self,
        *,
        resume_text: str,
        job_text: str,
        keyword: float,
        semantic: float,
        score: float,
    ) -> str: ...


class HeuristicExplainer:
    def explain(
        self,
        *,
        resume_text: str,
        job_text: str,
        keyword: float,
        semantic: float,
        score: float,
    ) -> str:
        fields = parse_job_fields(job_text)
        resume_terms = tokenize(resume_text)
        skill_terms = tokenize(fields.get("skills", "") or job_text)
        title_terms = tokenize(fields.get("title", ""))
        matched_skills = [term for term in skill_terms if term in resume_terms][:6]
        matched_title = [term for term in title_terms if term in resume_terms][:4]
        gaps = [term for term in skill_terms if term not in resume_terms][:6]
        parts = [f"Match score {score:.1f} (keyword {keyword:.1f}, semantic {semantic:.1f})."]
        if matched_skills:
            parts.append("Matched skills: " + ", ".join(matched_skills) + ".")
        if matched_title:
            parts.append("Title overlap: " + ", ".join(matched_title) + ".")
        if gaps:
            parts.append("Gaps: " + ", ".join(gaps) + ".")
        if not matched_skills and not matched_title:
            parts.append("Limited keyword overlap; score is driven by semantic similarity." if semantic else "Limited overlap overall.")
        text = _EMAIL.sub("[redacted]", " ".join(parts))
        return truncate_words(text, 500)


def default_explainer() -> Explainer:
    return HeuristicExplainer()

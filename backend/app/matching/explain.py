"""Explanation summaries for a match score."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from app.matching.boosts import SkillGate, skill_gate
from app.matching.spans import reason_spans
from app.matching.evidence import evidence_sentences
from app.matching.scoring import parse_job_fields, tokenize, truncate_words

_EMAIL = re.compile(r"\b\S+@\S+\.\S+\b")


@dataclass
class ExplainResult:
    summary: str
    highlights: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    gate: SkillGate | None = None
    spans: dict[str, list[dict[str, object]]] = field(default_factory=dict)


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
        return self.explain_structured(
            resume_text=resume_text,
            job_text=job_text,
            keyword=keyword,
            semantic=semantic,
            score=score,
        ).summary

    def explain_structured(
        self,
        *,
        resume_text: str,
        job_text: str,
        keyword: float,
        semantic: float,
        score: float,
    ) -> ExplainResult:
        fields = parse_job_fields(job_text)
        resume_terms = tokenize(resume_text)
        skill_terms = tokenize(fields.get("skills", "") or job_text)
        title_terms = tokenize(fields.get("title", ""))
        matched_skills = [term for term in skill_terms if term in resume_terms][:6]
        matched_title = [term for term in title_terms if term in resume_terms][:4]
        gaps = [term for term in skill_terms if term not in resume_terms][:6]
        gate = skill_gate(resume_text, job_text)
        evidence = evidence_sentences(resume_text, job_text, limit=5)
        parts = [f"Match score {score:.1f} (keyword {keyword:.1f}, semantic {semantic:.1f})."]
        if matched_skills:
            parts.append("Matched skills: " + ", ".join(matched_skills) + ".")
        if matched_title:
            parts.append("Title overlap: " + ", ".join(matched_title) + ".")
        if gaps:
            parts.append("Gaps: " + ", ".join(gaps) + ".")
        if gate.missing_required:
            parts.append("Missing must-haves: " + ", ".join(gate.missing_required[:4]) + ".")
        if not matched_skills and not matched_title:
            parts.append(
                "Limited keyword overlap; score is driven by semantic similarity."
                if semantic
                else "Limited overlap overall."
            )
        text = _EMAIL.sub("[redacted]", " ".join(parts))
        spans = reason_spans(job_text=job_text, highlights=matched_skills or matched_title, gaps=gaps)
        return ExplainResult(
            summary=truncate_words(text, 500),
            highlights=matched_skills or matched_title,
            gaps=gaps,
            evidence=evidence,
            gate=gate,
            spans=spans,
        )


def default_explainer() -> Explainer:
    return HeuristicExplainer()

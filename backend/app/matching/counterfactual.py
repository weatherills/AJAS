"""Counterfactual suggestions: skills to add to the resume to lift the score."""

from __future__ import annotations

from app.matching.boosts import skill_gate
from app.matching.gap_penalty import gap_penalty


def counterfactuals(resume_text: str, job_text: str, *, limit: int = 5) -> dict[str, object]:
    gate = skill_gate(resume_text, job_text)
    missing = list(gate.missing_required)[:limit]
    suggestions = [f"Add '{term}' to the resume (required on the posting)." for term in missing]
    if gate.nice_to_have:
        for term in gate.nice_to_have:
            if term not in gate.matched_nice and len(suggestions) < limit:
                suggestions.append(f"Consider adding '{term}' (preferred).")
    return {
        "add": missing,
        "suggestions": suggestions,
        "lift_if_all_added": round(gap_penalty(len(missing)), 2),
    }

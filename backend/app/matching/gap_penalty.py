"""Calibrated penalty when required skills are missing from the resume."""

from __future__ import annotations

from app.matching.boosts import skill_gate


def gap_penalty(missing_count: int, *, steepness: float = 0.18, cap: float = 35.0) -> float:
    if missing_count <= 0:
        return 0.0
    raw = 100.0 * (1.0 - pow(1.0 - steepness, missing_count))
    return round(min(cap, raw), 2)


def apply_gap_penalty(score: float, resume_text: str, job_text: str, **kwargs: float) -> dict[str, float | int]:
    gate = skill_gate(resume_text, job_text)
    missing = len(gate.missing_required)
    penalty = gap_penalty(missing, **kwargs)
    return {
        "base": float(score),
        "missing": missing,
        "penalty": penalty,
        "score": round(max(0.0, float(score) - penalty), 2),
    }

"""Classify resume bullets as achievements vs responsibilities."""

from __future__ import annotations

import re

_IMPACT = re.compile(r"\b(increased|reduced|saved|grew|launched|led|owned|improved|cut|delivered|built)\b", re.I)
_METRIC = re.compile(r"(\d+%|\$[\d,]+|\b\d+x\b)")
_DUTY = re.compile(r"^(responsible for|worked on|helped|assisted|participated)", re.I)


def classify_bullet(text: str) -> str:
    blob = (text or "").strip()
    if _METRIC.search(blob) or _IMPACT.search(blob):
        return "achievement"
    if _DUTY.search(blob):
        return "responsibility"
    return "responsibility"


def classify_resume(bullets: list[str]) -> dict[str, object]:
    rows = [{"text": item, "kind": classify_bullet(item)} for item in bullets]
    return {
        "bullets": rows,
        "achievements": sum(1 for row in rows if row["kind"] == "achievement"),
        "responsibilities": sum(1 for row in rows if row["kind"] == "responsibility"),
    }

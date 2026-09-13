"""Standardized benefits/perks schema extracted from job text."""

from __future__ import annotations

import re
from typing import Any

CANONICAL = (
    "health_insurance",
    "dental",
    "vision",
    "401k",
    "equity",
    "pto",
    "parental_leave",
    "remote_stipend",
    "learning_budget",
)

_PATTERNS: dict[str, re.Pattern[str]] = {
    "health_insurance": re.compile(r"\b(health|medical)\s+(insurance|plan|coverage)\b", re.I),
    "dental": re.compile(r"\bdental\b", re.I),
    "vision": re.compile(r"\bvision\b", re.I),
    "401k": re.compile(r"\b(401\s?\(?k\)?|pension|retirement)\b", re.I),
    "equity": re.compile(r"\b(equity|rsus?|stock options?)\b", re.I),
    "pto": re.compile(r"\b(pto|unlimited vacation|paid time off)\b", re.I),
    "parental_leave": re.compile(r"\b(parental|maternity|paternity)\s+leave\b", re.I),
    "remote_stipend": re.compile(r"\b(wfh|remote)\s+(stipend|allowance)\b", re.I),
    "learning_budget": re.compile(r"\b(learning|education|conference)\s+(budget|stipend)\b", re.I),
}


def extract_benefits(text: str | None) -> dict[str, Any]:
    blob = text or ""
    found = [key for key, pattern in _PATTERNS.items() if pattern.search(blob)]
    return {
        "schema": "ajas.benefits.v1",
        "benefits": found,
        "unknown": [],
        "canonical": list(CANONICAL),
    }

"""Highlight reason codes with character spans inside JD/resume text."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenSpan:
    code: str
    token: str
    start: int
    end: int
    source: str


def find_spans(text: str, tokens: list[str], *, code: str, source: str = "job") -> list[TokenSpan]:
    hay = text or ""
    lower = hay.lower()
    spans: list[TokenSpan] = []
    used: set[tuple[int, int]] = set()
    for token in tokens:
        needle = (token or "").strip()
        if len(needle) < 2:
            continue
        start = 0
        while True:
            idx = lower.find(needle.lower(), start)
            if idx < 0:
                break
            end = idx + len(needle)
            key = (idx, end)
            if key not in used:
                used.add(key)
                spans.append(TokenSpan(code=code, token=hay[idx:end], start=idx, end=end, source=source))
                break
            start = idx + 1
    spans.sort(key=lambda item: item.start)
    return spans


def reason_spans(*, job_text: str, highlights: list[str], gaps: list[str]) -> dict[str, list[dict[str, object]]]:
    matched = find_spans(job_text, highlights, code="matched_skill", source="job")
    missing = find_spans(job_text, gaps, code="missing_skill", source="job")
    return {
        "matched": [item.__dict__ for item in matched],
        "missing": [item.__dict__ for item in missing],
    }

"""Rebuild an experience timeline and infer gaps."""

from __future__ import annotations

import re
from datetime import date

_RANGE = re.compile(
    r"(?P<start>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}|\d{4})"
    r"\s*[-–to]+\s*"
    r"(?P<end>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}|\d{4}|present|current|now)",
    re.I,
)


def _parse_year(token: str) -> date | None:
    text = token.strip().lower()
    if text in {"present", "current", "now"}:
        return date.today()
    year = re.search(r"(\d{4})", text)
    if not year:
        return None
    month = 1
    months = "jan feb mar apr may jun jul aug sep oct nov dec".split()
    for index, name in enumerate(months, start=1):
        if text.startswith(name):
            month = index
            break
    return date(int(year.group(1)), month, 1)


def rebuild_timeline(bullets: list[str]) -> dict[str, object]:
    roles: list[dict[str, object]] = []
    for line in bullets:
        match = _RANGE.search(line or "")
        if not match:
            continue
        start = _parse_year(match.group("start"))
        end = _parse_year(match.group("end"))
        if not start or not end:
            continue
        roles.append({"raw": line, "start": start.isoformat(), "end": end.isoformat()})
    roles.sort(key=lambda item: str(item["start"]))
    gaps: list[dict[str, str]] = []
    for previous, current in zip(roles, roles[1:]):
        prev_end = date.fromisoformat(str(previous["end"]))
        next_start = date.fromisoformat(str(current["start"]))
        months = (next_start.year - prev_end.year) * 12 + (next_start.month - prev_end.month)
        if months >= 4:
            gaps.append({"after": str(previous["end"]), "before": str(current["start"])})
    return {"roles": roles, "gaps": gaps, "count": len(roles)}

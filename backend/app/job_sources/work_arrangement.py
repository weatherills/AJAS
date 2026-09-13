"""Onsite percentage and travel requirement fields."""

from __future__ import annotations

import re
from typing import Any

_ONSITE = re.compile(r"(\d{1,3})\s*%?\s*(onsite|in[- ]office|office)", re.I)
_REMOTE = re.compile(r"(\d{1,3})\s*%?\s*remote", re.I)
_DAYS = re.compile(r"(\d)\s*days?\s*(?:a|per)\s*week\s*(?:in[- ]office|onsite|office)", re.I)
_TRAVEL = re.compile(r"(?:travel|travelling)\s*(?:up to\s*)?(\d{1,3})\s*%", re.I)
_TRAVEL_WORDS = re.compile(r"\b(no travel|travel required|occasional travel|frequent travel)\b", re.I)


def work_arrangement(text: str | None) -> dict[str, Any]:
    blob = text or ""
    onsite: int | None = None
    remote: int | None = None
    travel: int | None = None
    travel_note = None
    match = _ONSITE.search(blob)
    if match:
        onsite = min(100, int(match.group(1)))
    days = _DAYS.search(blob)
    if days and onsite is None:
        onsite = min(100, int(round(100 * int(days.group(1)) / 5)))
    rem = _REMOTE.search(blob)
    if rem:
        remote = min(100, int(rem.group(1)))
    if onsite is None and remote is not None:
        onsite = 100 - remote
    if remote is None and onsite is not None:
        remote = 100 - onsite
    tr = _TRAVEL.search(blob)
    if tr:
        travel = min(100, int(tr.group(1)))
    words = _TRAVEL_WORDS.search(blob)
    if words:
        travel_note = words.group(1).lower()
        if travel is None and "no travel" in travel_note:
            travel = 0
        if travel is None and "frequent" in travel_note:
            travel = 50
        if travel is None and "occasional" in travel_note:
            travel = 10
        if travel is None and travel_note == "travel required":
            travel = 25
    return {
        "onsite_percent": onsite,
        "remote_percent": remote,
        "travel_percent": travel,
        "travel_note": travel_note,
    }

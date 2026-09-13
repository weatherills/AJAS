"""Education normalization v2 — degrees, majors, and school aliases."""

from __future__ import annotations

import re

DEGREES = {
    "bs": "bachelor",
    "b.s.": "bachelor",
    "bsc": "bachelor",
    "ba": "bachelor",
    "bachelor": "bachelor",
    "ms": "master",
    "m.s.": "master",
    "msc": "master",
    "ma": "master",
    "master": "master",
    "mba": "mba",
    "phd": "doctorate",
    "ph.d.": "doctorate",
    "doctorate": "doctorate",
}

SCHOOLS = {
    "mit": "Massachusetts Institute of Technology",
    "stanford": "Stanford University",
    "cmu": "Carnegie Mellon University",
    "oxon": "University of Oxford",
    "cantab": "University of Cambridge",
}


def normalize_education(line: str) -> dict[str, str | None]:
    hay = (line or "").strip()
    lower = hay.lower()
    compact = re.sub(r"[.]", "", lower)
    degree = None
    for token, canonical in DEGREES.items():
        needle = token.replace(".", "")
        if re.search(rf"\b{re.escape(needle)}\b", compact) or re.search(rf"\b{re.escape(token)}\b", lower):
            degree = canonical
            break
    school = None
    for alias, name in SCHOOLS.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            school = name
            break
    major = None
    major_match = re.search(r"\bin\s+([A-Za-z][A-Za-z &/]+?)(?:,|$)", hay)
    if major_match:
        major = major_match.group(1).strip()
    return {"raw": hay, "degree": degree, "school": school, "major": major}

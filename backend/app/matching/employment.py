"""Employment-type alignment between resume preference and job posting."""

from __future__ import annotations

import re

ALIASES = {
    "ft": "full_time",
    "full time": "full_time",
    "full-time": "full_time",
    "fulltime": "full_time",
    "pt": "part_time",
    "part time": "part_time",
    "part-time": "part_time",
    "contract": "contract",
    "contractor": "contract",
    "c2c": "contract",
    "intern": "intern",
    "internship": "intern",
}


def normalize_employment_type(text: str | None) -> str | None:
    blob = (text or "").strip().lower()
    if not blob:
        return None
    for key, value in ALIASES.items():
        if re.search(rf"\b{re.escape(key)}\b", blob):
            return value
    return None


def alignment(resume_pref: str | None, job_type: str | None) -> dict[str, object]:
    left = normalize_employment_type(resume_pref)
    right = normalize_employment_type(job_type)
    if not left or not right:
        return {"resume": left, "job": right, "aligned": None, "delta": 0.0}
    aligned = left == right
    return {"resume": left, "job": right, "aligned": aligned, "delta": 0.0 if aligned else -8.0}

"""Country-specific visa / work-authorization boosts and filters."""

from __future__ import annotations

import re

_RULES: dict[str, dict[str, float]] = {
    "US": {"sponsor": 3.0, "citizen_only": -8.0, "clearance": -4.0},
    "GB": {"sponsor": 2.0, "citizen_only": -6.0, "clearance": -3.0},
    "CA": {"sponsor": 2.5, "citizen_only": -6.0, "clearance": -2.0},
    "DE": {"sponsor": 2.0, "citizen_only": -5.0, "clearance": -2.0},
}

_SPONSOR = re.compile(r"\b(visa|sponsorship|h-?1b|skilled worker|blue card)\b", re.I)
_CITIZEN = re.compile(r"\b(citizen(ship)? required|no sponsorship|must be (a )?citizen)\b", re.I)
_CLEARANCE = re.compile(r"\b(security clearance|nv1|sc clearance)\b", re.I)


def visa_rules(job_text: str, resume_text: str, *, country: str = "US") -> dict[str, object]:
    table = _RULES.get((country or "US").upper(), _RULES["US"])
    hay_job = job_text or ""
    hay_resume = resume_text or ""
    boost = 0.0
    flags: list[str] = []
    if _CITIZEN.search(hay_job) and not _CITIZEN.search(hay_resume):
        boost += table["citizen_only"]
        flags.append("citizen_only")
    elif _SPONSOR.search(hay_job) and _SPONSOR.search(hay_resume):
        boost += table["sponsor"]
        flags.append("sponsor")
    if _CLEARANCE.search(hay_job) and not _CLEARANCE.search(hay_resume):
        boost += table["clearance"]
        flags.append("clearance")
    return {"country": country.upper(), "boost": round(boost, 2), "flags": flags}

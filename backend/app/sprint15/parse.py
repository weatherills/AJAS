"""Sprint 15 parse/normalize wrappers around Sprint 14 helpers."""

from __future__ import annotations

import re
from typing import Any

from app.sprint14.parse import contract_type, salary_bands, skills_negation, title_v3


def reset() -> None:
    return None


def seniority_v2(text: str) -> str:
    lowered = (text or "").lower()
    for key in ("intern", "junior", "mid", "senior", "staff", "principal"):
        if key in lowered:
            return key
    title = title_v3(text or "")
    blob = str(title.get("normalized") or "").lower()
    if "senior" in blob:
        return "senior"
    return "mid"


def remote_v2(text: str) -> str:
    lowered = (text or "").lower()
    if "hybrid" in lowered:
        return "hybrid"
    if "on-site" in lowered or "onsite" in lowered or "office" in lowered:
        return "onsite"
    if "remote" in lowered:
        return "remote"
    return "unspecified"


def education(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    degree = "unspecified"
    if "phd" in lowered or "doctor" in lowered:
        degree = "phd"
    elif "master" in lowered or "msc" in lowered or "mba" in lowered:
        degree = "masters"
    elif "bachelor" in lowered or "bs " in lowered or "ba " in lowered:
        degree = "bachelors"
    return {"degree": degree, "required": "degree" in lowered or degree != "unspecified"}


def yoe_band(text: str) -> dict[str, Any]:
    match = re.search(r"(\d+)\s*\+?\s*(?:years|yrs)", text or "", re.I)
    years = int(match.group(1)) if match else 0
    if years >= 8:
        band = "8+"
    elif years >= 5:
        band = "5-7"
    elif years >= 2:
        band = "2-4"
    else:
        band = "0-1"
    return {"years": years, "band": band}


def industry_v2(text: str) -> str:
    lowered = (text or "").lower()
    mapping = {
        "fintech": "finance",
        "bank": "finance",
        "health": "healthcare",
        "clinic": "healthcare",
        "game": "gaming",
        "saas": "software",
        "software": "software",
        "retail": "retail",
    }
    for needle, label in mapping.items():
        if needle in lowered:
            return label
    return "other"


def jd_v4(text: str) -> dict[str, Any]:
    required: list[str] = []
    nice: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip(" -*")
        if not stripped:
            continue
        if re.search(r"(?i)nice to have|plus|preferred", stripped):
            nice.append(stripped)
        elif re.search(r"(?i)must|required|need", stripped) or stripped.startswith("-"):
            required.append(stripped)
        else:
            required.append(stripped)
    return {"schema": "ajas.jd.v4", "required": required, "nice": nice, "contract": contract_type(text)}


def salary_v4(text: str) -> dict[str, Any]:
    base = salary_bands(text)
    lowered = (text or "").lower()
    period = "annual"
    if "hour" in lowered or "/hr" in lowered:
        period = "hourly"
    elif "day" in lowered or "/day" in lowered:
        period = "daily"
    return {**base, "period": period, "schema": "ajas.salary.v4"}


def skills_v4(text: str) -> dict[str, Any]:
    row = skills_negation(text)
    tools = [item for item in row.get("skills") or row.get("chunks") or [] if str(item).lower() in {"azure", "git", "docker", "k8s", "kubernetes"}]
    langs = [item for item in row.get("skills") or row.get("chunks") or [] if str(item).lower() in {"python", "go", "java", "typescript", "sql"}]
    return {**row, "tools": tools, "languages": langs, "schema": "ajas.skills.v4"}


def resume_v4(sections: list[str]) -> dict[str, Any]:
    order = ["summary", "experience", "skills", "education"]
    present = [name for name in order if any(name in (item or "").lower() for item in sections)]
    unknown = [item for item in sections if not any(name in (item or "").lower() for name in order)]
    return {"order": present + unknown, "repaired": present == order[: len(present)], "schema": "ajas.resume.v4"}


def alias_graph(parent: str, children: list[str]) -> dict[str, Any]:
    nodes = [parent, *children]
    return {"parent": parent, "children": children, "nodes": nodes, "edges": [(parent, child) for child in children]}

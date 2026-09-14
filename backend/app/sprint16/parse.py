"""Sprint 16 parse/normalize wrappers around Sprint 15 helpers."""

from __future__ import annotations

import re
from typing import Any

from app.sprint14.parse import contract_type
from app.sprint15.parse import industry_v2, resume_v4, salary_v4, skills_v4, title_v3


def reset() -> None:
    return None


def employment_v3(text: str) -> str:
    lowered = (text or "").lower()
    if "intern" in lowered:
        return "intern"
    if "part" in lowered:
        return "part_time"
    if "contract" in lowered or "c2c" in lowered:
        return "contract"
    return "full_time"


def work_auth_v2(text: str) -> dict[str, Any]:
    lowered = (text or "").lower()
    visa = "visa" in lowered or "h1b" in lowered or "sponsorship" in lowered
    citizen = "citizen" in lowered or "clearance" in lowered
    return {"visa": visa, "citizen": citizen, "required": visa or citizen}


def degree_alias(text: str) -> str:
    lowered = (text or "").lower()
    if "phd" in lowered or "doctorate" in lowered:
        return "phd"
    if "msc" in lowered or "master" in lowered or "mba" in lowered:
        return "masters"
    if "bsc" in lowered or "bachelor" in lowered or "bs " in lowered:
        return "bachelors"
    if "associate" in lowered:
        return "associates"
    return "unspecified"


def clearance(text: str) -> str:
    lowered = (text or "").lower()
    if "ts/sci" in lowered or "sci" in lowered:
        return "ts_sci"
    if "top secret" in lowered or "ts " in lowered:
        return "top_secret"
    if "secret" in lowered:
        return "secret"
    if "public trust" in lowered:
        return "public_trust"
    return "none"


def industry_naics(text: str) -> dict[str, Any]:
    label = industry_v2(text)
    codes = {"finance": "52", "healthcare": "62", "software": "51", "retail": "44", "gaming": "71"}
    return {"industry": label, "naics": codes.get(label, "99")}


def jd_v5(text: str) -> dict[str, Any]:
    quals: list[str] = []
    resp: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip(" -*")
        if not stripped:
            continue
        if re.search(r"(?i)qualif|require|must|degree|years", stripped):
            quals.append(stripped)
        else:
            resp.append(stripped)
    return {"schema": "ajas.jd.v5", "qualifications": quals, "responsibilities": resp, "contract": contract_type(text)}


def salary_v5(text: str) -> dict[str, Any]:
    base = salary_v4(text)
    lowered = (text or "").lower()
    overtime = "overtime" in lowered or "ot " in lowered
    equity = "equity" in lowered or "rsu" in lowered or "stock" in lowered
    return {**base, "overtime": overtime, "equity": equity, "schema": "ajas.salary.v5"}


def skills_v5(text: str) -> dict[str, Any]:
    row = skills_v4(text)
    certs = [item for item in row.get("skills") or row.get("chunks") or [] if str(item).lower() in {"aws", "azure", "gcp", "cissp", "pmp"}]
    tools = [item for item in row.get("tools") or [] if item]
    return {**row, "certs": certs, "tools": tools, "schema": "ajas.skills.v5"}


def resume_v5(sections: list[str]) -> dict[str, Any]:
    row = resume_v4(sections)
    dates = [item for item in sections if re.search(r"\d{4}", item or "")]
    overlap = len(dates) >= 2
    return {**row, "dateOverlap": overlap, "repaired": row.get("repaired") or overlap, "schema": "ajas.resume.v5"}


def brand_graph(dba: str, names: list[str]) -> dict[str, Any]:
    nodes = [dba, *names]
    return {"dba": dba, "names": names, "nodes": nodes, "edges": [(dba, name) for name in names]}


def title_clean(text: str) -> dict[str, Any]:
    return title_v3(text or "")

"""Sprint 14 parse/normalize wrappers around existing salary, geo, skills, resume helpers."""

from __future__ import annotations

from typing import Any

from app.job_sources.benefits import extract_benefits
from app.job_sources.comp import parse_comp
from app.job_sources.domain import resolve_company_domain
from app.job_sources.geocode import geocode
from app.matching.skills_v2 import extract_skills_v2
from app.matching.taxonomy import canonical_skill
from app.resumes.achievements import classify_bullet
from app.sprint13.parse import boilerplate_score, job_type, normalize_title_v3, salary_v3, to_usd


def reset() -> None:
    return None


def contract_type(text: str) -> str:
    return job_type(text)


def benefits_v2(text: str) -> dict[str, Any]:
    base = extract_benefits(text)
    visa = bool(__import__("re").search(r"(?i)\bvisa\b", text or ""))
    relocation = bool(__import__("re").search(r"(?i)\brelocation\b", text or ""))
    return {**base, "visa": visa, "relocation": relocation, "equity": "equity" in base.get("benefits", [])}


def skills_canon(tokens: list[str]) -> list[str]:
    return [canonical_skill(tok) for tok in tokens if tok.strip()]


def title_v3(title: str) -> dict[str, Any]:
    return normalize_title_v3(title)


def currency_tcc(text: str) -> dict[str, Any]:
    parsed = salary_v3(text)
    usd = to_usd(float(parsed.get("min") or parsed.get("amount") or 0), str(parsed.get("currency") or "USD"))
    tcc = "total" in (text or "").lower() or "tcc" in (text or "").lower() or "ote" in (text or "").lower()
    return {**parsed, "usdMin": usd, "tcc": tcc}


def geo_cache(city: str, state: str = "", country: str = "US") -> dict[str, Any]:
    return {**geocode(city, state, country), "cached": True}


def company_domain(name: str) -> dict[str, Any]:
    row = resolve_company_domain(name)
    return {"company": name, "domain": row.get("domain"), "via": row.get("method")}


def jd_sections(text: str) -> dict[str, Any]:
    boiler = boilerplate_score(text)
    bullets = [line.strip(" -*") for line in (text or "").splitlines() if line.strip().startswith(("-", "*"))]
    return {**boiler, "bullets": bullets, "schema": "ajas.jd.v3"}


def salary_bands(text: str) -> dict[str, Any]:
    return {**salary_v3(text), **parse_comp(text), "schema": "ajas.salary.v3"}


def skills_negation(text: str) -> dict[str, Any]:
    return {**extract_skills_v2(text), "schema": "ajas.skills.v3"}


def impact_bullets(lines: list[str]) -> dict[str, Any]:
    scored = [{"text": line, "kind": classify_bullet(line), "impact": classify_bullet(line) == "achievement"} for line in lines]
    return {"items": scored, "impactCount": sum(1 for row in scored if row["impact"])}

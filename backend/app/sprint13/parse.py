"""Resume/JD parsing v3, geocoding rollups, FX, salary equity, work mode, job type, titles."""

from __future__ import annotations

import re
from typing import Any

from app.job_sources.geocode import geocode
from app.job_sources.salary import parse_salary_v2
from app.resumes.achievements import classify_bullet
from app.resumes.gap_notes import annotate_gaps

_FX = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27, "CAD": 0.73, "AUD": 0.66}
_BOILER = re.compile(r"(?i)(equal opportunity|eoe|benefits include|we're a family|ping pong)")
_EQUITY = re.compile(r"(?i)(equity|rsu|options|refreshers?)\s*(?:of|:)?\s*\$?([\d,]+)?\s*(k)?")
_BONUS = re.compile(r"(?i)(bonus|ote)\s*(?:of|:)?\s*\$?([\d,]+)?\s*(k)?")
_REMOTE = re.compile(r"(?i)\b(remote|work from home|wfh|hybrid|onsite|on-site|in office)\b")
_TYPE = re.compile(r"(?i)\b(full[- ]?time|part[- ]?time|contract|intern|internship|freelance)\b")
_METRO = {
    "seattle": "seattle-tacoma",
    "bellevue": "seattle-tacoma",
    "redmond": "seattle-tacoma",
    "brooklyn": "new-york",
    "manhattan": "new-york",
    "austin": "austin",
}


def reset() -> None:
    return None


def gap_annotate(bullets: list[str], notes: dict[str, str] | None = None) -> dict[str, Any]:
    return annotate_gaps(bullets, notes=notes)


def achievement_metrics(text: str) -> dict[str, Any]:
    percents = re.findall(r"(\d+(?:\.\d+)?)%", text or "")
    money = re.findall(r"\$[\d,]+(?:k)?", text or "", flags=re.I)
    counts = re.findall(r"\b(\d{2,})\b", text or "")
    return {
        "kind": classify_bullet(text),
        "percents": [float(p) for p in percents],
        "money": money,
        "counts": [int(c) for c in counts[:8]],
        "hasMetric": bool(percents or money),
    }


def boilerplate_score(text: str) -> dict[str, Any]:
    hits = _BOILER.findall(text or "")
    ratio = min(1.0, len(hits) / 3)
    return {"hits": hits, "score": round(ratio, 3), "boilerplate": ratio >= 0.34}


def metro_rollup(city: str, state: str = "", country: str = "US") -> dict[str, Any]:
    geo = geocode(city, state, country)
    metro = _METRO.get((city or "").strip().lower())
    return {**geo, "metro": metro, "radiusKm": 40 if metro else 15}


def to_usd(amount: float, currency: str) -> float:
    return round(float(amount) * _FX.get((currency or "USD").upper(), 1.0), 2)


def display_money(amount_usd: float, currency: str) -> dict[str, Any]:
    code = (currency or "USD").upper()
    fx = _FX.get(code, 1.0)
    local = round(amount_usd / fx, 2) if fx else amount_usd
    return {"usd": amount_usd, "currency": code, "local": local, "fx": fx}


def salary_v3(text: str) -> dict[str, Any]:
    base = parse_salary_v2(text)
    equity = _EQUITY.search(text or "")
    bonus = _BONUS.search(text or "")

    def _amt(match: re.Match[str] | None) -> int | None:
        if not match or not match.group(2):
            return 0 if match else None
        raw = match.group(2).replace(",", "")
        value = float(raw)
        if match.group(3):
            value *= 1000
        return int(value)

    return {**base, "equity": _amt(equity), "bonus": _amt(bonus), "schema": "ajas.salary.v3"}


def work_mode(text: str) -> str:
    match = _REMOTE.search(text or "")
    if not match:
        return "unspecified"
    token = match.group(1).lower()
    if "hybrid" in token:
        return "hybrid"
    if "remote" in token or "wfh" in token or "home" in token:
        return "remote"
    return "onsite"


def job_type(text: str) -> str:
    match = _TYPE.search(text or "")
    if not match:
        return "unspecified"
    token = re.sub(r"[\s-]+", "", match.group(1).lower())
    mapping = {
        "fulltime": "ft",
        "parttime": "pt",
        "contract": "contract",
        "intern": "intern",
        "internship": "intern",
        "freelance": "contract",
    }
    return mapping.get(token, "unspecified")


def normalize_title_v3(title: str) -> dict[str, Any]:
    raw = re.sub(r"\s+", " ", (title or "").strip())
    low = raw.lower()
    aliases = {
        "swe": "software engineer",
        "sre": "site reliability engineer",
        "em": "engineering manager",
        "tpm": "technical program manager",
    }
    for short, full in aliases.items():
        if re.search(rf"\b{short}\b", low):
            low = re.sub(rf"\b{short}\b", full, low)
    return {"raw": raw, "normalized": low.title(), "key": re.sub(r"[^a-z0-9]+", "-", low).strip("-")}

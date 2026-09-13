"""JD cleaning, salary/seniority/location inference, and fuzzy title/company dedupe."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.matching.boosts import seniority_level, workplace_kind

_SECTION = re.compile(
    r"(?is)\n+(benefits|perks|what we offer|equal opportunity|eeo|privacy notice|"
    r"legal|compensation disclosure|about us)\s*:?\n"
)
_SALARY = re.compile(
    r"\$?\s*(\d{2,3}(?:,\d{3})?)(?:\s*k)?\s*(?:-|–|to)\s*\$?\s*(\d{2,3}(?:,\d{3})?)(?:\s*k)?",
    re.I,
)
_SINGLE = re.compile(r"\$\s*(\d{2,3}(?:,\d{3})?)(?:\s*k)?", re.I)
_HEADING = re.compile(
    r"(?im)^(responsibilities|about the role|what you.?ll do|requirements|qualifications|"
    r"must have|nice to have|benefits|about (?:us|the company)|equal opportunity)\s*:?\s*$"
)
_BULLET = re.compile(r"^(?:[\-\*•–]|\d+[.)]|[a-z][.)])\s+", re.I)


def clean_job_description(text: str) -> str:
    """Drop benefits/legalese/noise sections while keeping the role body."""
    raw = text or ""
    match = _SECTION.search(raw)
    if match:
        raw = raw[: match.start()]
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if _SECTION.match("\n" + stripped + "\n"):
            break
        lines.append(stripped)
    return "\n".join(lines).strip()


def normalize_bullet(line: str) -> str:
    stripped = (line or "").strip()
    if not stripped:
        return ""
    if _BULLET.match(stripped):
        return "- " + _BULLET.sub("", stripped).strip()
    return stripped


def clean_job_description_v2(text: str) -> dict[str, object]:
    """Section heuristics plus bullet normalization for JD bodies."""
    sections: dict[str, list[str]] = {}
    current = "body"
    for raw in (text or "").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        heading = _HEADING.match(stripped)
        if heading:
            current = heading.group(1).lower()
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(normalize_bullet(stripped))
    drop = {"benefits", "about us", "about the company", "equal opportunity"}
    kept_keys = [key for key in sections if key not in drop]
    lines: list[str] = []
    for key in kept_keys:
        if key != "body":
            lines.append(key.title() + ":")
        lines.extend(sections[key])
        lines.append("")
    cleaned = "\n".join(lines).strip()
    return {"text": cleaned, "sections": {key: sections[key] for key in kept_keys}, "bullets": [line for line in cleaned.splitlines() if line.startswith("- ")]}


def parse_salary(text: str) -> dict[str, int | None]:
    hay = text or ""
    match = _SALARY.search(hay)
    if match:
        return {"min": _to_annual(match.group(1)), "max": _to_annual(match.group(2))}
    single = _SINGLE.search(hay)
    if single:
        value = _to_annual(single.group(1))
        return {"min": value, "max": value}
    return {"min": None, "max": None}


def _to_annual(raw: str) -> int:
    digits = raw.replace(",", "")
    value = int(digits)
    if value < 1000:
        value *= 1000
    return value


def infer_location(text: str, fallback: str = "") -> dict[str, str]:
    workplace = workplace_kind(text or fallback)
    hay = (text or fallback or "").strip()
    city = fallback.strip() if fallback else ""
    if not city:
        loc_line = next((line.split(":", 1)[1].strip() for line in hay.splitlines() if line.lower().startswith("location:")), "")
        city = loc_line
    return {"workplace": workplace, "label": city or ("Remote" if workplace == "remote" else "")}


def infer_seniority(title: str, body: str = "") -> dict[str, object]:
    level = seniority_level(f"{title}\n{body}") or 3
    labels = {
        1: "intern",
        2: "junior",
        3: "mid",
        4: "senior",
        5: "staff",
        6: "principal",
        7: "director",
        8: "vp",
        9: "executive",
    }
    return {"level": level, "label": labels.get(level, "mid")}


def fuzzy_duplicate(left_title: str, left_company: str, right_title: str, right_company: str, *, threshold: float = 0.86) -> bool:
    title = SequenceMatcher(None, (left_title or "").lower(), (right_title or "").lower()).ratio()
    company = SequenceMatcher(None, (left_company or "").lower(), (right_company or "").lower()).ratio()
    return title >= threshold and company >= max(0.72, threshold - 0.1)


def enrich_posting(*, title: str, company: str, location: str, body: str) -> dict[str, object]:
    cleaned = clean_job_description(body)
    salary = parse_salary(cleaned or body)
    place = infer_location(f"{location}\n{cleaned}", location)
    senior = infer_seniority(title, cleaned)
    return {
        "title": title,
        "company": company,
        "location": place["label"] or location,
        "workplace": place["workplace"],
        "seniority": senior["label"],
        "seniorityLevel": senior["level"],
        "salaryMin": salary["min"],
        "salaryMax": salary["max"],
        "description": cleaned or body,
    }

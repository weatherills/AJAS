"""Rule boosts, must-have gating, and calibrated fit buckets."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.matching.scoring import parse_job_fields, tokenize
from app.matching.taxonomy import expand_terms

_REQUIRED_HEAD = re.compile(r"^(required|must have|must-have|requirements)\b", re.I)
_NICE_HEAD = re.compile(r"^(nice to have|nice-to-have|preferred|plus)\b", re.I)
_BULLET = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
_REMOTE = re.compile(r"\b(remote|work from home|wfh|distributed)\b", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.I)
_ONSITE = re.compile(r"\b(on[-\s]?site|in[-\s]?office)\b", re.I)
_VISA_SPONSOR = re.compile(r"\b(visa|h-?1b|sponsorship|opt|cpt)\b", re.I)
_CITIZEN = re.compile(r"\b(us citizen|u\.s\. citizen|citizenship required|no sponsorship)\b", re.I)

SENIORITY_LEVELS: tuple[tuple[str, int], ...] = (
    ("intern", 1),
    ("junior", 2),
    ("associate", 2),
    ("mid", 3),
    ("intermediate", 3),
    ("senior", 4),
    ("staff", 5),
    ("principal", 6),
    ("director", 7),
    ("vp", 8),
    ("chief", 9),
)

BUCKETS: tuple[tuple[int, str, str], ...] = (
    (85, "excellent", "Excellent match"),
    (70, "strong", "Strong match"),
    (55, "promising", "Promising match"),
    (40, "fair", "Fair match"),
    (0, "poor", "Poor match"),
)


@dataclass(frozen=True)
class SkillGate:
    required: list[str]
    nice_to_have: list[str]
    matched_required: list[str]
    missing_required: list[str]
    matched_nice: list[str]
    coverage: float


@dataclass(frozen=True)
class RuleBoosts:
    location: float
    seniority: float
    visa: float

    @property
    def total(self) -> float:
        return round(self.location + self.seniority + self.visa, 1)


def workplace_kind(text: str) -> str:
    hay = text or ""
    if _REMOTE.search(hay) and not _ONSITE.search(hay):
        return "remote"
    if _HYBRID.search(hay):
        return "hybrid"
    if _ONSITE.search(hay):
        return "onsite"
    return "unspecified"


def seniority_level(text: str) -> int | None:
    hay = (text or "").lower()
    best: int | None = None
    for token, level in SENIORITY_LEVELS:
        if re.search(rf"\b{re.escape(token)}\b", hay):
            best = level if best is None else max(best, level)
    return best


def _looks_like_skill_item(line: str) -> bool:
    """True for bullets or short skill phrases; false for JD body sentences."""
    if _BULLET.match(line):
        return True
    if line.endswith(".") or len(line) >= 60:
        return False
    words = re.findall(r"[A-Za-z][A-Za-z0-9+.#/-]*", line)
    return 1 <= len(words) <= 8


def _split_skill_lists(job_text: str) -> tuple[list[str], list[str]]:
    fields = parse_job_fields(job_text)
    required: list[str] = []
    nice: list[str] = []
    current: str | None = None
    allow_plain = False
    for raw in (job_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if _NICE_HEAD.match(line):
            current = "nice"
            rest = line.split(":", 1)[1] if ":" in line else ""
            if rest.strip():
                nice.extend(tokenize(rest))
                allow_plain = False
            else:
                allow_plain = True
            continue
        if _REQUIRED_HEAD.match(line):
            current = "required"
            rest = line.split(":", 1)[1] if ":" in line else ""
            if rest.strip():
                required.extend(tokenize(rest))
                allow_plain = False
            else:
                allow_plain = True
            continue
        if current in {"required", "nice"}:
            if _BULLET.match(line) or (allow_plain and _looks_like_skill_item(line)):
                target = required if current == "required" else nice
                target.extend(tokenize(line))
            else:
                current = None
    if not required:
        nice = tokenize(fields.get("skills") or "") + nice
    # de-dupe preserving order
    def _uniq(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out

    return _uniq(required), _uniq(nice)


def skill_gate(resume_text: str, job_text: str) -> SkillGate:
    required, nice = _split_skill_lists(job_text)
    resume_terms = expand_terms(tokenize(resume_text))
    matched_required = [term for term in required if canonical_in(term, resume_terms)]
    missing_required = [term for term in required if not canonical_in(term, resume_terms)]
    matched_nice = [term for term in nice if canonical_in(term, resume_terms)]
    coverage = (len(matched_required) / len(required)) if required else 1.0
    return SkillGate(
        required=required,
        nice_to_have=nice,
        matched_required=matched_required,
        missing_required=missing_required,
        matched_nice=matched_nice,
        coverage=round(coverage, 3),
    )


def canonical_in(term: str, haystack: set[str]) -> bool:
    from app.matching.taxonomy import canonical_skill

    return canonical_skill(term) in haystack or term.lower() in haystack


def rule_boosts(resume_text: str, job_text: str) -> RuleBoosts:
    resume_place = workplace_kind(resume_text)
    job_place = workplace_kind(job_text)
    location = 0.0
    if job_place == "remote" and resume_place in {"remote", "unspecified"}:
        location = 4.0
    elif resume_place == job_place and job_place != "unspecified":
        location = 4.0
    elif resume_place == "remote" and job_place == "onsite":
        location = -3.0
    elif job_place == "onsite" and resume_place == "unspecified":
        location = -1.0

    resume_level = seniority_level(resume_text)
    job_level = seniority_level(job_text)
    seniority = 0.0
    if resume_level is not None and job_level is not None:
        delta = resume_level - job_level
        if delta >= 0:
            seniority = min(5.0, 2.0 + delta)
        elif delta == -1:
            seniority = 0.0
        else:
            seniority = max(-8.0, delta * 3.0)

    visa = 0.0
    if _CITIZEN.search(job_text or "") and not _CITIZEN.search(resume_text or ""):
        visa = -8.0
    elif _VISA_SPONSOR.search(job_text or "") and _VISA_SPONSOR.search(resume_text or ""):
        visa = 3.0
    return RuleBoosts(location=location, seniority=seniority, visa=visa)


def apply_gate(score: float, gate: SkillGate) -> float:
    if not gate.required:
        return score
    if gate.coverage <= 0:
        return min(score, 39.0)
    if gate.coverage < 0.5:
        return min(score, 54.0)
    return score


def fit_bucket(score: float) -> dict[str, object]:
    shown = max(0, min(100, int(round(score))))
    for minimum, key, label in BUCKETS:
        if shown >= minimum:
            return {"key": key, "label": label, "min": minimum, "score": shown}
    return {"key": "poor", "label": "Poor match", "min": 0, "score": shown}

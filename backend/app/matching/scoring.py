"""Keyword scoring, cosine similarity, and word-safe truncation."""

from __future__ import annotations

import math
import re
from typing import Iterable, Mapping

KEYWORD_WEIGHTS_VERSION = "kw-fields-v1"
FIELD_WEIGHTS: dict[str, float] = {
    "title": 2.0,
    "skills": 1.5,
    "responsibilities": 1.0,
    "company": 0.25,
    "benefits": 0.25,
}
TERM_CAP = 2.0
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "this",
        "that",
        "it",
        "its",
        "we",
        "you",
        "they",
        "their",
        "our",
        "your",
        "i",
        "me",
        "my",
        "he",
        "she",
        "them",
        "his",
        "her",
        "not",
        "but",
        "if",
        "then",
        "so",
        "than",
        "too",
        "very",
        "can",
        "will",
        "just",
        "about",
        "into",
        "over",
        "after",
        "before",
        "also",
        "using",
        "use",
        "used",
        "via",
        "per",
        "within",
        "across",
        "including",
        "include",
        "such",
        "other",
        "more",
        "most",
        "some",
        "any",
        "all",
        "job",
        "role",
        "team",
        "work",
        "working",
        "experience",
        "responsible",
        "responsibilities",
        "requirement",
        "requirements",
        "skill",
        "skills",
        "benefit",
        "benefits",
        "company",
        "title",
        "description",
    }
)
_TOKEN = re.compile(r"[a-z0-9]+")
_LABEL = re.compile(
    r"^(title|company|skills|benefits|responsibilities|requirement|requirements)\s*:\s*(.*)$",
    re.IGNORECASE,
)


def stem(token: str) -> str:
    if len(token) <= 3:
        return token
    for suffix in ("ingly", "edly", "ing", "ers", "ies", "ied", "es", "ed", "ly", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            if suffix == "ies":
                return token[:-3] + "y"
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw in _TOKEN.findall((text or "").lower()):
        if raw in STOPWORDS or raw.isdigit():
            continue
        token = stem(raw)
        if token in STOPWORDS or len(token) < 2 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def parse_job_fields(job_text: str) -> dict[str, str]:
    fields = {name: "" for name in FIELD_WEIGHTS}
    unlabeled: list[str] = []
    lines = (job_text or "").splitlines()
    current = "responsibilities"
    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        match = _LABEL.match(line)
        if match:
            label = match.group(1).lower()
            if label in {"requirement", "requirements"}:
                label = "responsibilities"
            current = label if label in fields else "responsibilities"
            rest = match.group(2).strip()
            if rest:
                fields[current] = (fields[current] + " " + rest).strip()
            continue
        if index == 0 and len(line) <= 80 and not fields["title"]:
            fields["title"] = line
            continue
        unlabeled.append(line)
        fields[current] = (fields[current] + " " + line).strip()
    if not any(fields.values()):
        fields["responsibilities"] = job_text or ""
    elif unlabeled and not fields["responsibilities"]:
        fields["responsibilities"] = " ".join(unlabeled)
    return fields


def keyword_score(resume_text: str, job_text: str, job_fields: Mapping[str, str] | None = None) -> float:
    """Return a 0.0–1.0 keyword score with field weights and per-term caps."""
    resume_terms = tokenize(resume_text)
    if not resume_terms:
        return 0.0
    fields = dict(job_fields) if job_fields is not None else parse_job_fields(job_text)
    field_terms = {name: set(tokenize(fields.get(name, ""))) for name in FIELD_WEIGHTS}
    total = 0.0
    for term in resume_terms:
        contribution = 0.0
        for name, terms in field_terms.items():
            if term in terms:
                contribution += FIELD_WEIGHTS[name]
        total += min(contribution, TERM_CAP)
    denom = len(resume_terms) * TERM_CAP
    if denom <= 0:
        return 0.0
    return max(0.0, min(1.0, total / denom))


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    a = list(left)
    b = list(right)
    size = min(len(a), len(b))
    if size == 0:
        return 0.0
    a = a[:size]
    b = b[:size]
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * y for x, y in zip(b, b)))
    if na == 0.0 or nb == 0.0:
        return 0.0
    raw = dot / (na * nb)
    return max(0.0, min(1.0, raw))


def score_1dp(keyword_norm: float, semantic_norm: float, keyword_weight: float, semantic_weight: float) -> float:
    raw = 100.0 * (keyword_weight * keyword_norm + semantic_weight * semantic_norm)
    return round(max(0.0, min(100.0, raw)), 1)


def truncate_words(text: str, limit: int = 500) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;: ")

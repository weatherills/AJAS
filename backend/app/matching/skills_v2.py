"""Phrase chunking and negation-aware skill extraction."""

from __future__ import annotations

import re

from app.matching.scoring import STOPWORDS, tokenize

_NEGATION = re.compile(
    r"(?i)\b(not|no|without|except|excluding|don't need|do not need|isn't required|is not required)\b"
)
_PHRASE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/-]*(?:\s+[A-Za-z][A-Za-z0-9+.#/-]*){0,3}")


def phrase_chunks(text: str, *, max_n: int = 3) -> list[str]:
    tokens = [tok for tok in tokenize(text) if tok not in STOPWORDS]
    out: list[str] = []
    seen: set[str] = set()
    for n in range(max_n, 0, -1):
        for i in range(0, max(0, len(tokens) - n + 1)):
            phrase = " ".join(tokens[i : i + n])
            if phrase in seen:
                continue
            seen.add(phrase)
            out.append(phrase)
    return out


def _negated_window(text: str) -> set[str]:
    denied: set[str] = set()
    for raw in (text or "").splitlines():
        if not _NEGATION.search(raw):
            continue
        denied.update(tokenize(raw))
        for match in _PHRASE.finditer(raw):
            denied.add(match.group(0).lower())
    return denied


def extract_skills_v2(text: str) -> dict[str, list[str]]:
    chunks = phrase_chunks(text)
    denied = _negated_window(text)
    positive = [item for item in chunks if item not in denied and not any(tok in denied for tok in item.split())]
    negated = [item for item in chunks if item in denied or any(tok in denied for tok in item.split())]
    return {"skills": positive[:40], "negated": negated[:20], "chunks": chunks[:40]}

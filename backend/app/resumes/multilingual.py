"""Lightweight EN/ES/FR language detection for resume/JD parsing branches."""

from __future__ import annotations

MARKERS = {
    "es": ("el ", "la ", "los ", "las ", "experiencia", "educación", "habilidades"),
    "fr": ("le ", "la ", "les ", "expérience", "éducation", "compétences"),
    "en": ("the ", "and ", "experience", "education", "skills"),
}


def detect_lang(text: str) -> str:
    hay = f" {(text or '').lower()} "
    scores = {lang: sum(1 for token in tokens if token in hay) for lang, tokens in MARKERS.items()}
    best = max(scores, key=lambda lang: scores[lang])
    return best if scores[best] else "en"


def parse_branch(text: str) -> dict[str, str]:
    lang = detect_lang(text)
    return {"lang": lang, "parser": f"resume.{lang}"}

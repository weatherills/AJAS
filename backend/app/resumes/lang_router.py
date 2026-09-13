"""Route resume parsing to a language-specific branch."""

from __future__ import annotations

from app.resumes.multilingual import detect_lang, parse_branch

ROUTES = {"en": "en_us", "es": "es_es", "fr": "fr_fr"}


def route(text: str) -> dict[str, str]:
    branch = parse_branch(text)
    lang = branch["lang"]
    return {**branch, "route": ROUTES.get(lang, "en_us"), "detect": detect_lang(text)}

"""Matching keyword stemming, lemmatization, and word-safe truncation."""

from __future__ import annotations

from app.matching.scoring import (
    KEYWORD_WEIGHTS_VERSION,
    lemma,
    keyword_score,
    stem,
    tokenize,
    truncate_words,
)


def test_stem_strips_regular_suffixes():
    assert stem("kittens") == "kitten"
    assert stem("running") == "runn"
    assert lemma("running") == "run"
    assert lemma("engineers") == "engineer"
    assert stem("py") == "py"


def test_lemma_maps_irregulars_stem_cannot():
    assert lemma("better") == "good"
    assert lemma("wrote") == "write"
    assert lemma("written") == "write"
    assert lemma("ran") == "run"
    assert lemma("mice") == "mouse"
    assert lemma("management") == "manage"
    assert lemma("managers") == "manage"
    assert lemma("engineering") == "engineer"
    assert lemma("python") == "python"


def test_tokenize_matches_lemma_variants_not_only_exact_forms():
    resume = tokenize("I wrote python services and ran kubernetes")
    job = tokenize("Skills: write python. Responsibilities: run kubernetes")
    assert "write" in resume
    assert "write" in job
    assert "run" in resume
    assert "run" in job
    assert keyword_score(
        "I wrote python services and ran kubernetes clusters daily",
        "Title: Platform\nSkills: write python\nResponsibilities: run kubernetes",
    ) > keyword_score(
        "I wrote python services and ran kubernetes clusters daily",
        "Title: Baker\nSkills: frosting pastry",
    )


def test_management_and_managed_share_a_lemma():
    assert lemma("managed") == lemma("management")
    assert keyword_score(
        "Managed azure functions and python services",
        "Title: Engineering Manager\nSkills: python\nResponsibilities: cloud management",
    ) > 0


def test_lemma_covers_empty_ment_and_ation_forms():
    assert lemma("") == ""
    assert lemma("   ") == ""
    assert lemma("companies") == "company"
    assert lemma("computation") == "compute"
    assert lemma("engagement") == "engage"
    assert stem("happily") == "happi"
    text = "Matched skills: python azure cosmos functions kubernetes terraform extra"
    cut = truncate_words(text, 40)
    assert len(cut) <= 40
    assert not cut.endswith("func")
    assert " " not in cut[-1:]
    assert truncate_words("short", 500) == "short"
    assert KEYWORD_WEIGHTS_VERSION == "kw-lemma-v1"

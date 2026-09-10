"""Public board token / URL parsing (SSRF-safe tenant keys)."""

import pytest

from app.job_sources.errors import JobSourceValidationError
from app.job_sources.urls import parse_board_input


def test_parse_plain_tokens():
    assert parse_board_input("greenhouse", token="Acme") == "acme"
    assert parse_board_input("lever", token="open-ai") == "open-ai"


def test_parse_greenhouse_urls():
    assert parse_board_input("greenhouse", url="https://boards.greenhouse.io/stripe") == "stripe"
    assert parse_board_input("greenhouse", url="https://boards.greenhouse.io/Stripe/jobs/123") == "stripe"
    assert (
        parse_board_input("greenhouse", url="https://boards-api.greenhouse.io/v1/boards/figma/jobs") == "figma"
    )


def test_parse_lever_urls():
    assert parse_board_input("lever", url="https://jobs.lever.co/openai") == "openai"
    assert parse_board_input("lever", url="https://jobs.lever.co/openai/staff-engineer") == "openai"
    assert parse_board_input("lever", url="https://api.lever.co/v0/postings/notion?mode=json") == "notion"


def test_parse_rejects_empty_and_ssrf():
    with pytest.raises(JobSourceValidationError):
        parse_board_input("greenhouse")
    with pytest.raises(JobSourceValidationError):
        parse_board_input("greenhouse", url="https://evil.example/acme")
    with pytest.raises(JobSourceValidationError):
        parse_board_input("lever", url="http://jobs.lever.co/acme")
    with pytest.raises(JobSourceValidationError):
        parse_board_input("greenhouse", token="acme/../admin")

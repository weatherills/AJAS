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


def test_lever_list_jobs_stops_on_short_page():
    from app.job_sources.constants import LEVER_PAGE_LIMIT
    from app.job_sources.normalize import lever_list_jobs

    short, nxt = lever_list_jobs([{"id": "a"}, {"id": "b"}], limit=LEVER_PAGE_LIMIT)
    assert len(short) == 2
    assert nxt is None
    full, nxt = lever_list_jobs([{"id": str(i)} for i in range(LEVER_PAGE_LIMIT)], limit=LEVER_PAGE_LIMIT)
    assert len(full) == LEVER_PAGE_LIMIT
    assert nxt == str(LEVER_PAGE_LIMIT)
    empty, nxt = lever_list_jobs([])
    assert empty == []
    assert nxt is None


def test_domain_slot_caps_in_flight():
    from contextlib import ExitStack

    from app.job_sources.constants import MAX_IN_FLIGHT_PER_DOMAIN
    from app.job_sources.errors import JobSourceRateLimitedError
    from app.job_sources.global_limit import domain_slot

    url = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"
    with ExitStack() as stack:
        for _ in range(MAX_IN_FLIGHT_PER_DOMAIN):
            stack.enter_context(domain_slot(url, timeout=0.05))
        with pytest.raises(JobSourceRateLimitedError):
            with domain_slot(url, timeout=0.05):
                pass
    with domain_slot(url, timeout=0.05):
        pass

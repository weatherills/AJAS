"""Fixture parsers for company career pages that embed Greenhouse/Lever/Workday.

These are not live scrapers. HTML is operator-supplied. Robots/consent still
fail closed via load_fixture_jobs when a listing_url is provided.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from app.job_sources.boards import load_fixture_jobs

_ATTR = re.compile(r'data-ajas-(\w+)="([^"]*)"')


class _JobCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.jobs: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        mapping = {key: (value or "") for key, value in attrs}
        if "data-ajas-job" not in mapping:
            return
        self.jobs.append(
            {
                "id": mapping.get("data-id") or "",
                "title": mapping.get("data-title") or "",
                "company": mapping.get("data-company") or "",
                "location": mapping.get("data-location") or "",
                "apply_url": mapping.get("data-apply") or mapping.get("href") or "",
                "employment_type": mapping.get("data-type") or "",
                "description": mapping.get("data-description") or "",
            }
        )


def parse_career_html(html: str) -> list[dict[str, str]]:
    parser = _JobCardParser()
    parser.feed(html or "")
    return [job for job in parser.jobs if job.get("title") and job.get("apply_url")]


def _from_html(source: str, html: str, listing_url: str | None) -> list[dict[str, Any]]:
    jobs = parse_career_html(html)
    return load_fixture_jobs(source, {"jobs": jobs}, listing_url=listing_url)


def greenhouse_career_jobs(html: str, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    return _from_html("greenhouse_career", html, listing_url)


def lever_career_jobs(html: str, *, listing_url: str | None = None) -> list[dict[str, Any]]:
    return _from_html("lever_career", html, listing_url)

"""Sprint 11 task tests. Grows one commit at a time."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings

FIXTURES = Path(__file__).parent / "fixtures"


def _enable_zip(monkeypatch) -> None:
    monkeypatch.setenv("FLAG_ZIPRECRUITER_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)


def test_ziprecruiter_cursor_pages_and_retry_after(monkeypatch):
    from app.job_sources.ziprecruiter import paginate, retry_after_seconds, ziprecruiter_jobs

    payload = json.loads((FIXTURES / "job_boards" / "ziprecruiter_pages.json").read_text())
    pages = paginate(payload)
    assert [job["id"] for job in pages] == ["zr-p1", "zr-p2"]
    assert retry_after_seconds(payload, 0) == 1.5
    _enable_zip(monkeypatch)
    rows = ziprecruiter_jobs(payload, listing_url="https://fixtures.ajas.local/ziprecruiter")
    assert [row["source_posting_id"] for row in rows] == ["zr-p1", "zr-p2"]
    monkeypatch.setenv("FLAG_ZIPRECRUITER_ADAPTER", "false")
    get_settings.cache_clear()
    assert ziprecruiter_jobs(payload) == []


def test_hired_adapter_auth_and_captcha_fallback(monkeypatch):
    from app.job_sources.hired import auth_gate, clear_token, hired_jobs, remember_token

    payload = json.loads((FIXTURES / "job_boards" / "hired.json").read_text())
    clear_token()
    monkeypatch.setenv("FLAG_HIRED_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    monkeypatch.delenv("HIRED_API_TOKEN", raising=False)
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    blocked = auth_gate("<div class='g-recaptcha'></div>")
    assert blocked.captcha is True
    assert blocked.action == "needs_manual"
    assert blocked.bypass is False
    assert hired_jobs(payload, html="<div class='hcaptcha'></div>") == []
    assert hired_jobs(payload) == []
    remember_token("hired-dev-token")
    rows = hired_jobs(payload, listing_url="https://fixtures.ajas.local/hired")
    assert rows and rows[0]["source_posting_id"] == "hi-1"
    clear_token()
    monkeypatch.setenv("FLAG_HIRED_ADAPTER", "false")
    get_settings.cache_clear()
    remember_token("hired-dev-token")
    assert hired_jobs(payload) == []
    clear_token()

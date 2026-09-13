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


def test_greenhouse_career_page_fixture_parser(monkeypatch):
    from app.job_sources.career_pages import greenhouse_career_jobs, parse_career_html

    html = (FIXTURES / "job_boards" / "greenhouse_career.html").read_text()
    cards = parse_career_html(html)
    assert [card["id"] for card in cards] == ["gh-c-1", "gh-c-2"]
    monkeypatch.setenv("FLAG_GREENHOUSE_CAREER_ADAPTER", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = greenhouse_career_jobs(html, listing_url="https://fixtures.ajas.local/greenhouse")
    assert rows[0]["title"] == "Staff Platform Engineer"
    monkeypatch.setenv("FLAG_GREENHOUSE_CAREER_ADAPTER", "false")
    get_settings.cache_clear()
    assert greenhouse_career_jobs(html) == []


def test_lever_career_page_fixture_parser(monkeypatch):
    from app.job_sources.career_pages import lever_career_jobs

    html = (FIXTURES / "job_boards" / "lever_career.html").read_text()
    monkeypatch.setenv("FLAG_LEVER_CAREER_ADAPTER", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = lever_career_jobs(html, listing_url="https://fixtures.ajas.local/lever")
    assert rows[0]["source_posting_id"] == "lv-c-1"
    assert rows[0]["company"] == "Fabrikam"
    monkeypatch.setenv("FLAG_LEVER_CAREER_ADAPTER", "false")
    get_settings.cache_clear()
    assert lever_career_jobs(html) == []


def test_workday_career_page_fixture_parser(monkeypatch):
    from app.job_sources.career_pages import workday_career_jobs

    html = (FIXTURES / "job_boards" / "workday_career.html").read_text()
    monkeypatch.setenv("FLAG_WORKDAY_ADAPTER", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = workday_career_jobs(html, listing_url="https://fixtures.ajas.local/workday")
    assert rows[0]["source_posting_id"] == "wd-c-1"
    assert "Workday" in rows[0]["title"]
    monkeypatch.setenv("FLAG_WORKDAY_ADAPTER", "false")
    get_settings.cache_clear()
    assert workday_career_jobs(html) == []


def test_source_adapter_watchdog_retries_on_dom_drift():
    from app.job_sources.drift import reset
    from app.job_sources.watchdog import retry_on_drift

    reset()
    payloads = [
        {"jobs": [{"id": "1"}], "etag": "a"},
        {"jobs": [{"id": "1"}], "ts": "later"},
        {"jobs": [{"id": "2", "title": "New"}]},
    ]
    calls: list[int] = []

    def loader(payload):
        calls.append(1)
        jobs = payload.get("jobs") if isinstance(payload, dict) else []
        return jobs

    first = retry_on_drift("canary-src", payloads[0], loader)
    assert first["attempts"] == 1
    assert first["recovered"] is True
    same_shape = retry_on_drift("canary-src", payloads[1], loader)
    assert same_shape["changed"] is False
    drifted = retry_on_drift("canary-src", payloads[2], loader)
    assert drifted["changed"] is True
    assert drifted["jobs"] == [{"id": "2", "title": "New"}]
    assert len(calls) >= 3


def test_source_adapter_canary_html_snapshot_drift(tmp_path):
    from app.job_sources.canary import check_snapshot, run_canaries

    html = tmp_path / "board.html"
    html.write_text("<div>v1</div>")
    (tmp_path / "board.html.sha256").write_text("deadbeef\n")
    bad = check_snapshot("board.html", tmp_path)
    assert bad["ok"] is False
    (tmp_path / "board.html.sha256").write_text(bad["digest"] + "\n")
    good = check_snapshot("board.html", tmp_path)
    assert good["ok"] is True
    batch = run_canaries(["greenhouse_career.html", "lever_career.html", "workday_career.html"])
    assert batch["ok"] is True
    assert batch["checked"] == 3

"""Sprint 10 task tests. Grows one commit at a time."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.job_sources.boards import backoff_seconds, glassdoor_jobs, iter_pages

FIXTURES = Path(__file__).parent / "fixtures"


def test_glassdoor_paginates_fixtures_when_flag_on(monkeypatch):
    payload = json.loads((FIXTURES / "job_boards" / "glassdoor.json").read_text())
    assert len(iter_pages(payload)) == 2
    assert backoff_seconds(0) == 0.25
    assert backoff_seconds(3) == 2.0
    assert backoff_seconds(10) == 8.0
    monkeypatch.setenv("FLAG_GLASSDOOR_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = glassdoor_jobs(payload, listing_url="https://fixtures.ajas.local/glassdoor")
    assert [row["source_posting_id"] for row in rows] == ["gd-1", "gd-2"]
    assert rows[1]["page"] == 2
    monkeypatch.setenv("FLAG_GLASSDOOR_ADAPTER", "false")
    get_settings.cache_clear()
    assert glassdoor_jobs(payload) == []


def test_wellfound_requires_token_and_flag(monkeypatch):
    from app.job_sources import boards as boards_mod
    from app.job_sources.boards import wellfound_jobs
    from app.job_sources.wellfound_auth import auth_status, clear_token, remember_token

    payload = json.loads((FIXTURES / "job_boards" / "wellfound.json").read_text())
    clear_token()
    monkeypatch.setenv("FLAG_WELLFOUND_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    monkeypatch.delenv("WELLFOUND_API_TOKEN", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    assert auth_status().token_present is False
    assert wellfound_jobs(payload, listing_url="https://fixtures.ajas.local/wellfound") == []
    remember_token("wf-dev-token")
    rows = wellfound_jobs(payload, listing_url="https://fixtures.ajas.local/wellfound")
    assert rows and rows[0]["source_posting_id"] == "wf-1"
    clear_token()
    monkeypatch.setenv("FLAG_WELLFOUND_ADAPTER", "false")
    get_settings.cache_clear()


def test_rotating_user_agents_and_retry_jitter():
    from app.job_sources.http_policy import jittered_backoff, rotate_user_agent

    assert rotate_user_agent(index=0) == "AJASJobIngest/1.0"
    assert rotate_user_agent(seed="glassdoor") in {
        "AJASJobIngest/1.0",
        "AJASJobIngest/1.0 (+https://ajas.local/ops)",
        "AJASJobIngest/1.1",
    }
    delay = jittered_backoff(1, jitter=0.0)
    assert delay == 0.5
    noisy = jittered_backoff(2, jitter=0.3)
    assert 0 <= noisy <= 8.0


def test_circuit_breaker_opens_after_repeated_5xx():
    from app.job_sources.circuit import allow, record_status, reset, snapshot

    reset("glassdoor")
    for _ in range(4):
        snap = record_status("glassdoor", 503)
        assert snap.disabled is False
    snap = record_status("glassdoor", 503)
    assert snap.disabled is True
    assert allow("glassdoor") is False
    assert snapshot("glassdoor").open is True
    record_status("glassdoor", 200)
    assert allow("glassdoor") is True


def test_company_domain_resolver_mx_then_whois():
    from app.job_sources.domain import resolve_company_domain

    hinted = resolve_company_domain("Acme Labs", hint="https://www.acme.io/jobs")
    assert hinted == {"domain": "acme.io", "method": "hint", "company": "Acme Labs"}
    mx = resolve_company_domain("Northwind", mx_lookup=lambda domain: domain, whois_lookup=lambda _: None)
    assert mx["domain"] == "northwind.com" and mx["method"] == "mx"
    whois = resolve_company_domain("Contoso", mx_lookup=lambda _: None, whois_lookup=lambda name: "contoso.net")
    assert whois == {"domain": "contoso.net", "method": "whois", "company": "Contoso"}

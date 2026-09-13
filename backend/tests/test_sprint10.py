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


def test_geocode_city_state_country_is_cached():
    from app.job_sources.geocode import clear_cache, geocode

    clear_cache()
    first = geocode("Seattle", "WA", "US")
    second = geocode("Seattle", "WA", "US")
    assert first["found"] is True
    assert first["lat"] == 47.6062
    assert first["lon"] == -122.3321
    assert second["cached"] is True
    missing = geocode("Atlantis", "OC", "US")
    assert missing["found"] is False
    assert missing["lat"] is None


def test_jd_text_cleaner_v2_sections_and_bullets():
    from app.job_sources.enrich import clean_job_description_v2

    raw = """
About the role
Build the matching pipeline
Responsibilities
* Own ingestion
1) Ship ranking
Benefits
Free snacks
"""
    cleaned = clean_job_description_v2(raw)
    assert "Benefits:" not in cleaned["text"]
    assert "- Own ingestion" in cleaned["bullets"]
    assert "- Ship ranking" in cleaned["bullets"]
    assert "responsibilities" in cleaned["sections"]
    assert "benefits" not in cleaned["sections"]


def test_salary_parsing_v2_multi_currency_and_total_comp():
    from app.job_sources.salary import parse_salary_v2

    euro = parse_salary_v2("EUR 90k-110k total compensation")
    assert euro["min"] == 90000
    assert euro["max"] == 110000
    assert euro["currency"] == "EUR"
    assert euro["totalComp"] is True
    gbp = parse_salary_v2("£75,000-£95,000")
    assert gbp["currency"] == "GBP"
    assert gbp["min"] == 75000
    assert gbp["totalComp"] is False
    usd = parse_salary_v2("OTE $180k including equity")
    assert usd["min"] == 180000
    assert usd["currency"] == "USD"
    assert usd["totalComp"] is True


def test_skill_extractor_v2_phrases_and_negation():
    from app.matching.skills_v2 import extract_skills_v2

    result = extract_skills_v2("Required: Python and machine learning.\nNo Java.\nWithout Kubernetes.")
    skills = " ".join(result["skills"])
    negated = " ".join(result["negated"])
    assert "python" in skills
    assert "machine learn" in skills or "machine" in skills
    assert "java" in negated
    assert "kubernet" in negated or "kubernetes" in negated
    assert "java" not in skills.split()


def test_resume_parser_v2_project_impact_scoring():
    from app.resumes.impact import extract_and_score

    text = """
Projects
- Launched matching v2 and increased interview rate 32%
- Owned on-call rotation
Experience:
- Various duties
"""
    result = extract_and_score(text)
    assert result["bullets"]
    top = result["top"][0]
    assert "32%" in top["text"] or "32" in "".join(top["metrics"])
    assert int(top["score"]) >= 80
    assert result["impactScore"] > 0


def test_embeddings_reindex_sweeper_retries_then_indexes():
    from app.matching.reindex import ReindexSweeper

    calls = {"n": 0}

    def flaky(texts: list[str]) -> list[list[float]]:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("embed timeout")
        return [[0.1, 0.2] for _ in texts]

    sweeper = ReindexSweeper(embed=flaky, max_attempts=3)
    sweeper.enqueue("job-1", "python azure matching")
    first = sweeper.sweep(limit=1)
    assert first["retried"] == 1
    second = sweeper.sweep(limit=1)
    assert second["indexed"] == 1
    assert "job-1" in sweeper.indexed


def test_vector_store_tombstone_and_vacuum():
    from app.matching.vectors import VectorStore

    store = VectorStore()
    store.upsert("a", [1.0, 0.0])
    store.upsert("b", [0.0, 1.0])
    store.delete("a")
    assert store.get("a") is None
    store.live["a"] = [1.0, 0.0]
    result = store.vacuum()
    assert "a" not in store.live
    assert result["live"] == 1
    assert result["tombstones"] == 1


def test_matching_recency_time_decay():
    from datetime import datetime, timezone, timedelta
    from app.matching.recency import recency_boost

    now = datetime(2026, 9, 13, tzinfo=timezone.utc)
    fresh = recency_boost((now - timedelta(days=1)).isoformat(), now=now)
    stale = recency_boost((now - timedelta(days=45)).isoformat(), now=now)
    missing = recency_boost(None, now=now)
    assert fresh > stale
    assert fresh > 4
    assert stale < 1.5
    assert missing == 0.0


def test_matching_fairness_dedupes_near_identical_roles():
    from app.matching.fairness import dedupe_roles

    rows = [
        {"title": "Staff Engineer", "company": "Acme", "score": 70},
        {"title": "Staff Engineer", "company": "Acme", "score": 88},
        {"title": "Product Designer", "company": "Acme", "score": 60},
    ]
    kept = dedupe_roles(rows)
    titles = [(row["title"], row["score"]) for row in kept]
    assert ("Staff Engineer", 88) in titles
    assert ("Staff Engineer", 70) not in titles
    assert ("Product Designer", 60) in titles


def test_isotonic_regression_scaffold_with_holdout():
    from app.matching.isotonic import holdout_split, isotonic_fit, isotonic_predict

    pairs = [(10, 0.1), (20, 0.4), (30, 0.2), (40, 0.8), (50, 0.9)]
    split = holdout_split(pairs, holdout_frac=0.2)
    assert split.holdout
    fitted = isotonic_fit(split.train)
    xs = [x for x, _ in fitted]
    ys = [y for _, y in fitted]
    assert xs == sorted(xs)
    assert ys == sorted(ys)
    mid = isotonic_predict(fitted, 25)
    assert ys[0] <= mid <= ys[-1]


def test_explanation_reason_codes_include_token_spans():
    from app.matching.spans import reason_spans

    job = "We need Python and Azure experience. Kubernetes is required."
    spans = reason_spans(job_text=job, highlights=["Python", "Azure"], gaps=["Kubernetes"])
    assert spans["matched"][0]["code"] == "matched_skill"
    assert job[spans["matched"][0]["start"] : spans["matched"][0]["end"]].lower() == "python"
    assert spans["missing"][0]["code"] == "missing_skill"
    assert spans["missing"][0]["token"].lower() == "kubernetes"


def test_job_description_diff_versions():
    from app.job_sources.diff import diff_job_description

    previous = "Build crawlers.\nOwn ranking."
    current = "Build crawlers.\nOwn ranking and explanations."
    diff = diff_job_description(previous, current)
    assert diff["changed"] is True
    assert diff["added"] >= 1
    assert "+++ current" in diff["unified"]


def test_apply_field_mapping_overrides():
    from app.auto_apply.field_map import apply_mapping, reset_overrides, set_override

    reset_overrides()
    profile = {"full_name": "Ada Lovelace", "email": "ada@example.com"}
    assert apply_mapping("lever", profile)["name"] == "Ada Lovelace"
    set_override("lever", {"full_name": "candidate_name"})
    assert apply_mapping("lever", profile)["candidate_name"] == "Ada Lovelace"


def test_cover_letter_tone_presets():
    from app.auto_apply.cover_tone import render_cover

    concise = render_cover(role="Staff Engineer", company="Acme", name="Ada", tone="concise")
    enthusiastic = render_cover(role="Staff Engineer", company="Acme", name="Ada", tone="enthusiastic")
    formal = render_cover(role="Staff Engineer", company="Acme", name="Ada", tone="formal")
    assert "Staff Engineer" in concise["text"]
    assert "excited" in enthusiastic["text"].lower()
    assert "consideration" in formal["text"].lower()
    assert concise["label"] == "Concise"


def test_resume_profiles_with_tags():
    from app.resumes.profiles import ResumeProfile, list_profiles, reset_profiles, upsert_profile

    reset_profiles()
    upsert_profile("ada", ResumeProfile("p1", "r1", "Staff backend", ["backend", "remote"]))
    upsert_profile("ada", ResumeProfile("p2", "r2", "Frontend", ["frontend"]))
    assert len(list_profiles("ada")) == 2
    remote = list_profiles("ada", tag="remote")
    assert [row.label for row in remote] == ["Staff backend"]


def test_imap_labels_map_to_internal_states():
    from app.mail.imap_labels import map_label, map_labels

    assert map_label("AJAS/Interview") == "interview"
    mapped = map_labels(["Inbox", "AJAS/Applied"])
    assert mapped["current"] == "applied"


def test_sender_reputation_warmup_and_daily_cap():
    from datetime import date
    from app.mail.reputation import ReputationState, can_send, daily_cap

    assert daily_cap(age_days=0) == 5
    assert daily_cap(age_days=14) > daily_cap(age_days=1)
    day_one = can_send(ReputationState(day=date(2026, 9, 13), sent=5, age_days=0))
    assert day_one["allowed"] is False
    warmed = can_send(ReputationState(day=date(2026, 9, 13), sent=5, age_days=10))
    assert warmed["allowed"] is True


def test_reply_templates_v2_placeholders_and_preview():
    from app.mail.templates_v2 import preset, render_template

    rendered = render_template("Hi {{first_name}} at {{company}}", {"first_name": "Ada"})
    assert rendered["complete"] is False
    assert "company" in rendered["missing"]
    full = preset("interested", {"first_name": "Ada", "role": "Staff", "company": "Acme"})
    assert "Ada" in full["preview"]
    assert full["complete"] is True

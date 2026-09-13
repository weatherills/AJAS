from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "job_boards"

# === S14-01 ===

def test_ziprecruiter_adapter_v1_pagination_backoff():
    from app.flags import feature_enabled
    from app.sprint14 import VERSION
    from app.features.health import _status_payload
    from app.sprint14.ingest import reset, ziprecruiter_v1

    reset()
    assert VERSION == "sprint14"
    assert _status_payload()["version"] == "sprint14"
    assert feature_enabled("ziprecruiter_adapter") is False
    payload = json.loads((FIXTURES / "ziprecruiter.json").read_text())
    out = ziprecruiter_v1(payload)
    assert out["live"] is False
    assert out["flag"] is False
    assert len(out["jobs"]) >= 2

# === S14-02 ===

def test_monster_adapter_v1_html_api_hybrid():
    from app.sprint14.ingest import monster_v1, reset

    reset()
    out = monster_v1(payload={"jobs": [{"id": "1", "title": "Staff"}]}, html="<div>job posting</div>")
    assert "json" in out["paths"] and "html" in out["paths"]
    assert out["flag"] is False

# === S14-03 ===

def test_hired_adapter_v1_with_auth_session():
    from app.job_sources.hired import clear_token
    from app.sprint14.ingest import hired_v1, reset

    reset()
    clear_token()
    gated = hired_v1({"jobs": []})
    assert gated["bypass"] is False
    assert gated["action"] in {"needs_auth", "continue"}
    captcha = hired_v1({"jobs": []}, html="please complete the captcha")
    assert captcha["bypass"] is False
    assert captcha["action"] == "needs_manual"

# === S14-04 ===

def test_remoteok_adapter_v1():
    from app.sprint14.ingest import remoteok_v1, reset

    reset()
    out = remoteok_v1({"jobs": [{"id": "1", "title": "Remote Python"}]})
    assert out["jobs"][0]["title"] == "Remote Python"
    assert out["live"] is False

# === S14-05 ===

def test_remotive_adapter_v1():
    from app.sprint14.ingest import remotive_v1, reset

    reset()
    out = remotive_v1({"jobs": [{"id": "1", "title": "Remotive Role"}]})
    assert out["source"] == "remotive"
    assert out["flag"] is False

# === S14-06 ===

def test_weworkremotely_adapter_v1():
    from app.sprint14.ingest import reset, wwr_v1

    reset()
    out = wwr_v1(html="<article data-ajas-job data-title='WWR' data-company='Co' data-apply='https://x'></article>")
    assert out["flag"] is False
    assert out["live"] is False

# === S14-07 ===

def test_workable_adapter_v1():
    from app.sprint14.ingest import reset, workable_v1

    reset()
    out = workable_v1({"results": [{"id": "w1", "title": "Workable"}]})
    assert out["jobs"][0]["via"] == "json"

# === S14-08 ===

def test_greenhouse_company_board_crawler():
    from app.sprint14.ingest import greenhouse_board, reset

    reset()
    html = (FIXTURES / "greenhouse_career.html").read_text()
    out = greenhouse_board(html)
    assert out["crawler"] == "fixture"
    assert out["live"] is False
    assert any("Staff" in str(job.get("title")) for job in out["jobs"])

# === S14-09 ===

def test_lever_company_board_crawler():
    from app.sprint14.ingest import lever_board, reset

    reset()
    html = (FIXTURES / "lever_career.html").read_text()
    out = lever_board(html)
    assert out["source"] == "lever"
    assert out["live"] is False

# === S14-10 ===

def test_ashby_company_board_crawler():
    from app.sprint14.ingest import ashby_board, reset

    reset()
    out = ashby_board(payload={"jobs": [{"id": "a1", "title": "Ashby Role"}]})
    assert out["crawler"] == "fixture"
    assert out["flag"] is False

# === S14-11 ===

def test_source_adapter_bot_challenge_auto_detect_fallback():
    from app.sprint14.ingest import bot_challenge, reset

    reset()
    hit = bot_challenge("hcaptcha challenge")
    assert hit["captcha"] is True and hit["bypass"] is False and hit["fallback"] == "fixture"
    ok = bot_challenge("normal job html")
    assert ok["ok"] is True and ok["bypass"] is False

# === S14-12 ===

def test_source_adapter_rotating_proxies_abstraction_health():
    from app.sprint14.ingest import proxy_health, reset

    reset()
    row = proxy_health("http://proxy.ajas.local:8080")
    assert row["healthy"] is True
    assert row["active"]

# === S14-13 ===

def test_source_adapter_robots_txt_crawl_delay_compliance_toggle():
    from app.sprint14.ingest import reset, robots_toggle

    reset()
    row = robots_toggle("https://example.com/jobs", respect=True)
    assert row["respect"] is True
    assert row["allow"] is False

# === S14-14 ===

def test_source_adapter_centralized_backoff_jitter_policy():
    from app.sprint14.ingest import backoff_policy, reset

    reset()
    later = backoff_policy(4)
    early = backoff_policy(1)
    assert later["delaySec"] >= early["delaySec"]
    assert later["jitter"] is True

# === S14-15 ===

def test_source_adapter_http_fingerprint_randomization():
    from app.sprint14.ingest import fingerprint, reset

    reset()
    one = fingerprint("board-a")
    two = fingerprint("board-b")
    assert one["randomized"] is True
    assert one["ua"] and two["ua"]

# === S14-16 ===

def test_normalization_contract_types():
    from app.sprint14.parse import contract_type

    assert contract_type("Full-time role") == "ft"
    assert contract_type("Internship") == "intern"
    assert contract_type("Contract") == "contract"

# === S14-17 ===

def test_normalization_benefits_parsing():
    from app.sprint14.parse import benefits_v2

    row = benefits_v2("Visa sponsorship, relocation, and equity RSUs. Health insurance.")
    assert row["visa"] is True
    assert row["relocation"] is True
    assert "health_insurance" in row["benefits"] or row["equity"]

# === S14-18 ===

def test_normalization_skills_canonicalization_v3():
    from app.sprint14.parse import skills_canon

    assert "python" in skills_canon(["py", "Python3"])

# === S14-19 ===

def test_normalization_title_cleaning_rules_v3():
    from app.sprint14.parse import title_v3

    assert "Software Engineer" in title_v3("Senior SWE")["normalized"]

# === S14-20 ===

def test_normalization_currency_normalization_tcc_note():
    from app.sprint14.parse import currency_tcc

    row = currency_tcc("$140,000-$165,000 total compensation")
    assert row["tcc"] is True
    assert row["usdMin"] > 0

# === S14-21 ===

def test_geocoding_city_state_country_lat_lon_cache():
    from app.sprint14.parse import geo_cache

    sea = geo_cache("Seattle", "WA")
    assert sea["found"] is True
    assert sea["cached"] is True
    assert sea["lat"]

# === S14-22 ===

def test_company_domain_resolver_via_dns_mx_whois_fallback():
    from app.sprint14.parse import company_domain

    row = company_domain("Contoso")
    assert str(row["domain"]).endswith(".com")
    assert row["via"] in {"mx", "whois", "guess", "hint"}

# === S14-23 ===

def test_jd_cleaner_v3_section_heuristics_bullets():
    from app.sprint14.parse import jd_sections

    row = jd_sections("Equal opportunity employer.\n- Build APIs\n- Own ingest")
    assert row["schema"] == "ajas.jd.v3"
    assert row["bullets"]

# === S14-24 ===

def test_salary_parsing_v3_multi_currency_bands():
    from app.sprint14.parse import salary_bands

    row = salary_bands("$120k-$150k plus equity of $50k")
    assert row["min"]
    assert row["schema"] == "ajas.salary.v3"

# === S14-25 ===

def test_skill_extractor_v3_phrase_chunker_negation():
    from app.sprint14.parse import skills_negation

    row = skills_negation("Need python and azure. Not java.")
    assert row["schema"] == "ajas.skills.v3"
    assert row["chunks"]

# === S14-26 ===

def test_resume_parser_v3_impact_bullets_scoring():
    from app.sprint14.parse import impact_bullets

    row = impact_bullets(["Increased conversion 12%", "Responsible for on-call"])
    assert row["impactCount"] >= 1

# === S14-27 ===

def test_embeddings_incremental_reindex_sweeper_retries():
    from app.sprint14.matching import reindex_sweep, reset

    reset()
    out = reindex_sweep([("d1", "python azure"), ("d2", "react")])
    assert out["indexed"] == 2
    assert out["processed"] == 2

# === S14-28 ===

def test_vector_store_compaction_tombstone_vacuum_job_v2():
    from app.sprint14.matching import reset, vacuum_v2

    reset()
    out = vacuum_v2()
    assert out["schema"] == "ajas.vector.vacuum.v2"
    assert "live" in out

# === S14-29 ===

def test_matching_recency_time_decay_factor_v2():
    from app.sprint14.matching import recency_v2

    assert recency_v2(months_ago=6) > recency_v2(months_ago=40)

# === S14-30 ===

def test_matching_dedupe_near_identical_roles_per_company_v2():
    from app.sprint14.matching import dedupe_v2

    rows = dedupe_v2([{"id": "a", "company": "Acme", "score": 1}, {"id": "b", "company": "Acme", "score": 9}])
    assert len(rows) == 1
    assert rows[0]["id"] == "b"

# === S14-31 ===

def test_matching_multilingual_jd_support_detect_translate():
    from app.sprint14.matching import multilingual_jd

    es = multilingual_jd("Experiencia laboral y habilidades")
    assert es["lang"] == "es"
    assert es["translate"] is True

# === S14-32 ===

def test_ranking_feedback_logging_for_ltr():
    from app.sprint14.matching import ltr_event, reset

    reset()
    row = ltr_event(user_id="ada@example.test", job_id="j1", event="reply")
    assert row["event"] == "reply"
    assert "@" not in row["userId"]

# === S14-33 ===

def test_ranking_pairwise_training_data_generator():
    from app.sprint14.matching import pairwise_rows

    pairs = pairwise_rows([{"id": "a", "score": 90}, {"id": "b", "score": 10}])
    assert pairs[0]["chosen"] == "a"

# === S14-34 ===

def test_ranking_calibration_monitor_dashboard_v2():
    from app.sprint14.matching import calibration_monitor

    row = calibration_monitor([91, 80, 40])
    assert row["n"] == 3
    assert row["A"] >= 1


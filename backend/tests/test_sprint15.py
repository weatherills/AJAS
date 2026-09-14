from __future__ import annotations

# === S15-01 ===

def test_indeed_adapter_v1_pagination_backoff():
    from app.flags import feature_enabled
    from app.sprint15 import VERSION
    from app.features.health import _status_payload
    from app.sprint15.ingest import indeed_v1, reset

    reset()
    assert VERSION == "sprint15"
    assert _status_payload()["version"] == "sprint15"
    assert feature_enabled("indeed_adapter") is False
    out = indeed_v1({"jobs": [{"id": "1", "title": "Backend"}, {"id": "2", "title": "Data"}]})
    assert out["live"] is False and out["flag"] is False
    assert len(out["jobs"]) >= 2
    assert out["pages"] is True

# === S15-02 ===

def test_dice_adapter_v1():
    from app.sprint15.ingest import dice_v1, reset
    reset()
    out = dice_v1({"jobs": [{"id": "d1", "title": "Dice Role"}]})
    assert out["source"] == "dice" and out["live"] is False

# === S15-03 ===

def test_wellfound_adapter_v1():
    from app.sprint15.ingest import reset, wellfound_v1
    reset()
    out = wellfound_v1({"jobs": [{"id": "w1", "title": "Founding Eng"}]})
    assert out["jobs"][0]["title"] == "Founding Eng"
    assert out["flag"] is False

# === S15-04 ===

def test_linkedin_jobs_adapter_v1_fixture_only():
    from app.sprint15.ingest import linkedin_v1, reset
    reset()
    out = linkedin_v1({"jobs": [{"id": "l1", "title": "Staff"}]})
    assert out["live"] is False
    assert out["flag"] is False

# === S15-05 ===

def test_google_for_jobs_adapter_v1():
    from app.sprint15.ingest import google_jobs_v1, reset
    reset()
    out = google_jobs_v1({"jobs": [{"id": "g1", "title": "SWE"}]})
    assert out["flag"] is False

# === S15-06 ===

def test_otta_adapter_v1():
    from app.sprint15.ingest import otta_v1, reset
    reset()
    out = otta_v1({"jobs": [{"id": "o1", "title": "Otta Role"}]})
    assert out["source"] == "otta"

# === S15-07 ===

def test_yc_work_at_a_startup_adapter_v1():
    from app.sprint15.ingest import reset, yc_v1
    reset()
    out = yc_v1({"jobs": [{"id": "y1", "title": "YC Eng"}]})
    assert out["live"] is False

# === S15-08 ===

def test_flexjobs_adapter_v1():
    from app.sprint15.ingest import flexjobs_v1, reset
    reset()
    out = flexjobs_v1({"jobs": [{"id": "f1", "title": "Flex"}]})
    assert out["flag"] is False

# === S15-09 ===

def test_simplyhired_adapter_v1():
    from app.sprint15.ingest import reset, simplyhired_v1
    reset()
    out = simplyhired_v1({"jobs": [{"id": "s1", "title": "Simply"}]})
    assert out["jobs"]

# === S15-10 ===

def test_careerbuilder_adapter_v1():
    from app.sprint15.ingest import careerbuilder_v1, reset
    reset()
    out = careerbuilder_v1({"jobs": [{"id": "c1", "title": "CB"}]})
    assert out["live"] is False and out["flag"] is False

# === S15-11 ===

def test_source_adapter_tls_fingerprint_pin_rotate():
    from app.sprint15.ingest import reset, tls_fingerprint
    reset()
    row = tls_fingerprint("seed-a")
    assert row["pinned"] is True and row["rotated"] is True
    assert row["ja3"]

# === S15-12 ===

def test_source_adapter_cookie_jar_session_pool():
    from app.sprint15.ingest import cookie_jar, reset
    reset()
    row = cookie_jar("example.test")
    assert row["live"] is False and row["pool"] is True

# === S15-13 ===

def test_source_adapter_retry_after_header_honor():
    from app.sprint15.ingest import reset, retry_after
    reset()
    row = retry_after({"Retry-After": "3"}, 1)
    assert row["waitSec"] == 3 and row["honored"] is True

# === S15-14 ===

def test_source_adapter_sitemap_xml_board_discovery():
    from app.sprint15.ingest import reset, sitemap_boards
    reset()
    row = sitemap_boards("<urlset><url><loc>https://jobs.example.test/a</loc></url></urlset>")
    assert row["live"] is False
    assert any("jobs.example.test" in url for url in row["urls"])

# === S15-15 ===

def test_source_adapter_rss_atom_feed_boards():
    from app.sprint15.ingest import reset, rss_boards
    reset()
    row = rss_boards("<rss><item><title>Staff Python</title></item></rss>")
    assert "Staff Python" in row["titles"]
    assert row["live"] is False

# === S15-16 ===

def test_source_adapter_stale_listing_ttl():
    from app.sprint15.ingest import reset, stale_ttl
    reset()
    assert stale_ttl(age_hours=72)["stale"] is True
    assert stale_ttl(age_hours=1)["stale"] is False

# === S15-17 ===

def test_source_adapter_per_host_concurrency_caps():
    from app.sprint15.ingest import host_caps, reset
    reset()
    assert host_caps(host="a.test", inflight=2)["allow"] is False
    assert host_caps(host="a.test", inflight=0)["allow"] is True

# === S15-18 ===

def test_source_adapter_consent_cookie_fail_closed_v2():
    from app.sprint15.ingest import consent_v2, reset
    reset()
    blocked = consent_v2("https://jobs.example.test/x", consent=False)
    assert blocked["allow"] is False
    assert blocked["failClosed"] is True

# === S15-19 ===

def test_source_adapter_html_vs_json_path_selector():
    from app.sprint15.ingest import path_selector, reset
    reset()
    assert path_selector(json_ok=True, html=None) == "json"
    assert path_selector(json_ok=False, html="<div>job posting</div>") == "html"

# === S15-20 ===

def test_source_adapter_etag_if_none_match_cache():
    from app.sprint15.ingest import etag_cache, reset
    reset()
    assert etag_cache(etag="abc", incoming="abc")["notModified"] is True
    assert etag_cache(etag="abc", incoming="zzz")["hit"] is False

# === S15-21 ===

def test_normalization_seniority_ladder_v2():
    from app.sprint15.parse import seniority_v2
    assert seniority_v2("Senior Software Engineer") == "senior"
    assert seniority_v2("internship") == "intern"

# === S15-22 ===

def test_normalization_remote_hybrid_onsite_v2():
    from app.sprint15.parse import remote_v2
    assert remote_v2("Remote-first") == "remote"
    assert remote_v2("Hybrid 3 days") == "hybrid"
    assert remote_v2("On-site Seattle") == "onsite"

# === S15-23 ===

def test_normalization_education_requirements():
    from app.sprint15.parse import education
    row = education("Bachelor's degree required")
    assert row["degree"] == "bachelors"
    assert row["required"] is True

# === S15-24 ===

def test_normalization_years_of_experience_bands():
    from app.sprint15.parse import yoe_band
    row = yoe_band("5+ years of Python")
    assert row["years"] == 5
    assert row["band"] == "5-7"

# === S15-25 ===

def test_normalization_industry_taxonomy_v2():
    from app.sprint15.parse import industry_v2
    assert industry_v2("Fintech SaaS payments") in {"finance", "software"}

# === S15-26 ===

def test_jd_cleaner_v4_requirements_vs_nice_to_have():
    from app.sprint15.parse import jd_v4
    row = jd_v4("Must have Python\nNice to have Go")
    assert row["schema"] == "ajas.jd.v4"
    assert row["required"] and row["nice"]

# === S15-27 ===

def test_salary_parsing_v4_hourly_daily_annual():
    from app.sprint15.parse import salary_v4
    row = salary_v4("$80/hour contract")
    assert row["period"] == "hourly"
    assert row["schema"] == "ajas.salary.v4"

# === S15-28 ===

def test_skill_extractor_v4_tool_vs_language_split():
    from app.sprint15.parse import skills_v4
    row = skills_v4("Need python and azure. Not java.")
    assert row["schema"] == "ajas.skills.v4"
    assert row["chunks"]

# === S15-29 ===

def test_resume_parser_v4_section_order_repair():
    from app.sprint15.parse import resume_v4
    row = resume_v4(["Summary", "Experience at Acme", "Skills python", "Education BS"])
    assert row["schema"] == "ajas.resume.v4"
    assert row["repaired"] is True

# === S15-30 ===

def test_company_alias_graph_parent_subsidiaries():
    from app.sprint15.parse import alias_graph
    row = alias_graph("Contoso", ["Northwind", "Fabrikam"])
    assert row["parent"] == "Contoso"
    assert len(row["edges"]) == 2

# === S15-31 ===

def test_embeddings_delta_checksum_skip_unchanged():
    from app.sprint15.matching import delta_checksum, reset
    reset()
    seen = {}
    first = delta_checksum("d1", "python azure", seen)
    second = delta_checksum("d1", "python azure", seen)
    assert first["skip"] is False
    assert second["skip"] is True

# === S15-32 ===

def test_vector_store_replica_lag_detector():
    from app.sprint15.matching import replica_lag, reset
    reset()
    row = replica_lag(replica_ms=10, primary_ms=12)
    assert row["healthy"] is True

# === S15-33 ===

def test_matching_location_radius_boost():
    from app.sprint15.matching import location_boost
    assert location_boost(km=0) == 1.0
    assert location_boost(km=50) == 0.0
    assert location_boost(km=10) > location_boost(km=40)

# === S15-34 ===

def test_matching_title_family_clustering():
    from app.sprint15.matching import title_family
    assert title_family("Engineering Manager") == "mgmt"
    assert title_family("Data Analyst") == "data"

# === S15-35 ===

def test_matching_compensation_band_overlap():
    from app.sprint15.matching import comp_overlap
    row = comp_overlap(120, 160, 140, 180)
    assert row["hit"] is True
    assert row["overlap"] > 0

# === S15-36 ===

def test_ranking_listwise_ltr_features_v2():
    from app.sprint15.matching import listwise_v2
    rows = listwise_v2([{"id": "a", "score": 1}, {"id": "b", "score": 9}])
    assert rows[0]["id"] == "b" and rows[0]["rank"] == 1

# === S15-37 ===

def test_ranking_exploration_exploitation_epsilon():
    from app.sprint15.matching import epsilon_explore
    assert epsilon_explore(score=0.9, epsilon=0.1, draw=0.2) == "exploit"
    assert epsilon_explore(score=0.9, epsilon=0.1, draw=0.01) == "explore"

# === S15-38 ===

def test_explanations_why_not_this_role():
    from app.sprint15.matching import why_not
    row = why_not(["Python"], ["Python", "SQL"])
    assert row["missing"] == ["SQL"]

# === S15-39 ===

def test_fit_score_confidence_interval():
    from app.sprint15.matching import confidence
    row = confidence(keyword=1, semantic=1, recency=1)
    assert row["total"] == 1
    assert row["interval"] == 1

# === S15-40 ===

def test_diversity_de_bias_title_tokens():
    from app.sprint15.matching import debias_title
    assert "ninja" not in debias_title("Code ninja").lower()

# === S15-41 ===

def test_filters_shared_team_presets():
    from app.sprint15.product import list_team_presets, reset, team_preset
    reset()
    team_preset(team_id="t1", name="python", filters={"q": "python"})
    assert list_team_presets("t1")[0]["name"] == "python"
    assert list_team_presets("t2") == []

# === S15-42 ===

def test_search_boolean_query_parser():
    from app.sprint15.product import boolean_search
    hits = boolean_search([{"title": "Staff Python", "company": "Acme"}], "python AND acme")
    assert len(hits) == 1

# === S15-43 ===

def test_job_list_virtualized_grid_mode():
    from app.sprint15.product import grid_mode
    row = grid_mode(n=40, start=0)
    assert row["mode"] == "grid"

# === S15-44 ===

def test_job_detail_company_insights_panel():
    from app.sprint15.product import company_insights
    row = company_insights("Acme")
    assert row["live"] is False and row["panel"] is True

# === S15-45 ===

def test_bulk_actions_bulk_save_undo():
    from app.sprint15.product import bulk_save
    row = bulk_save(["a", "b", "c"], ["b", "z"])
    assert row["saved"] == ["b"]
    assert row["undo"] == ["b"]

# === S15-46 ===

def test_apply_required_field_checklist():
    from app.sprint15.product import required_fields
    row = required_fields("greenhouse", {"name": "Ada", "email": "a@b.c", "resume": "r1"})
    assert row["ready"] is True
    assert required_fields("lever", {"name": "Ada"})["missing"]


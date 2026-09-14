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


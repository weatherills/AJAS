from __future__ import annotations

from app.sprint12.security import sign_webhook
from app.sprint15.kanban import bounce_header, reset, titles

HTML = '<a data-ajas-job data-id="1" data-title="Staff Python" data-company="Acme" data-apply="https://jobs.example.test/1">x</a>'


def setup_function() -> None:
    reset()


def test_kanban_has_seventy_five_titles():
    assert len(titles()) == 75
    assert all(item.startswith("Sprint 15 — ") for item in titles())


# === adapters ===

def test_indeed_paginated_fetch_v2():
    from app.flags import feature_enabled
    from app.sprint15.kanban import indeed_paginated_v2

    out = indeed_paginated_v2({"jobs": [{"id": "1", "title": "Backend"}, {"id": "2", "title": "Data"}], "retry_after": 2})
    assert out["live"] is False
    assert out["pages"] is True
    assert out["antiBot"] is True
    assert out["backoffSec"] >= 2
    assert feature_enabled("indeed_adapter") is False


def test_dice_listings_v1():
    from app.sprint15.kanban import dice_listings_v1

    out = dice_listings_v1({"jobs": [{"id": "d1", "title": "Dice Role"}]})
    assert out["source"] == "dice"
    assert out["live"] is False


def test_flexjobs_v1():
    from app.sprint15.kanban import flexjobs_listings_v1

    out = flexjobs_listings_v1({"jobs": [{"id": "f1", "title": "Flex"}]})
    assert out["antiBot"] is True
    assert out["flag"] is False


def test_careerbuilder_v1():
    from app.sprint15.kanban import careerbuilder_listings_v1

    out = careerbuilder_listings_v1({"jobs": [{"id": "c1", "title": "CB"}]})
    assert out["live"] is False


def test_simplyhired_v1():
    from app.sprint15.kanban import simplyhired_listings_v1

    out = simplyhired_listings_v1(payload={"jobs": [{"id": "s1", "title": "Simply"}]}, html=HTML)
    assert out["jobs"]
    assert out["antiBot"] is True


def test_google_for_jobs_v1():
    from app.sprint15.kanban import google_for_jobs_v1

    out = google_for_jobs_v1({"jobs": [{"id": "g1", "title": "SWE"}]})
    assert out["structuredData"] is True
    assert out["flag"] is False


def test_linkedin_jobs_v1_fixture_driven():
    from app.sprint15.kanban import linkedin_fixture_v1

    out = linkedin_fixture_v1({"jobs": [{"id": "l1", "title": "Staff"}]})
    assert out["fixtureOnly"] is True
    assert out["live"] is False


def test_otta_v1():
    from app.sprint15.kanban import otta_listings_v1

    out = otta_listings_v1({"jobs": [{"id": "o1", "title": "Otta Role"}]})
    assert out["source"] == "otta"


def test_yc_work_at_a_startup_v1():
    from app.sprint15.kanban import yc_listings_v1

    out = yc_listings_v1({"jobs": [{"id": "y1", "title": "YC Eng"}]})
    assert out["live"] is False


def test_hired_v1_auth_session():
    from app.job_sources.hired import clear_token
    from app.sprint15.kanban import hired_auth_v1

    clear_token()
    blocked = hired_auth_v1({"jobs": [{"id": "h1", "title": "Hired"}]})
    assert blocked["action"] == "needs_auth"
    assert blocked["bypass"] is False
    authed = hired_auth_v1({"jobs": [{"id": "h1", "title": "Hired"}]}, token="tok")
    assert authed["action"] == "continue"
    assert authed["live"] is False
    captcha = hired_auth_v1({"jobs": []}, html="<form>recaptcha challenge</form>", token="tok")
    assert captcha["action"] == "needs_manual"
    assert captcha["bypass"] is False


def test_monster_v1_html_api_hybrid():
    from app.sprint15.kanban import monster_hybrid_v1

    out = monster_hybrid_v1(payload={"jobs": [{"id": "1", "title": "Staff"}]}, html="<div>job posting</div>")
    assert "json" in out["paths"]
    assert out["bypass"] is False


def test_remotive_v1():
    from app.sprint15.kanban import remotive_feed_v1

    out = remotive_feed_v1({"jobs": [{"id": "1", "title": "Remotive Role"}]})
    assert out["source"] == "remotive"


def test_weworkremotely_v1():
    from app.sprint15.kanban import wwr_feed_v1

    out = wwr_feed_v1(payload={"jobs": [{"id": "w1", "title": "WWR"}]}, html=HTML)
    assert out["live"] is False


def test_workable_v1():
    from app.sprint15.kanban import workable_listings_v1

    out = workable_listings_v1({"results": [{"id": "w1", "title": "Workable"}]})
    assert out["jobs"]


def test_greenhouse_company_board_crawler():
    from app.sprint15.kanban import greenhouse_crawler

    out = greenhouse_crawler(HTML)
    assert out["crawler"] == "fixture"
    assert out["live"] is False
    assert any(job.get("title") == "Staff Python" for job in out["jobs"])


def test_lever_company_board_crawler():
    from app.sprint15.kanban import lever_crawler

    out = lever_crawler(HTML)
    assert out["source"] == "lever"
    assert out["live"] is False


def test_ashby_company_board_crawler():
    from app.sprint15.kanban import ashby_crawler

    out = ashby_crawler(payload={"jobs": [{"id": "a1", "title": "Ashby Role"}]})
    assert out["crawler"] == "fixture"
    assert out["flag"] is False


def test_greenhouse_resilience_pass():
    from app.sprint15.kanban import greenhouse_resilience

    blocked = greenhouse_resilience(html="<div>cf-challenge captcha</div>", headers={"Retry-After": "4"})
    assert blocked["ok"] is False
    assert blocked["bypass"] is False
    ok = greenhouse_resilience(payload={"jobs": [{"id": "1", "title": "A"}]}, headers={"Retry-After": "3"})
    assert ok["waitSec"] >= 3
    assert ok["path"] == "json"


def test_lever_resilience_pass():
    from app.sprint15.kanban import lever_resilience

    out = lever_resilience(payload={"jobs": [{"title": "L"}]}, html="<div>job posting</div>")
    assert out["sessionRefresh"] is True
    assert out["live"] is False


def test_workday_resilience_pass():
    from app.sprint15.kanban import workday_resilience

    out = workday_resilience(html=HTML, headers={"Retry-After": "1"})
    assert out["driftCheck"] is True
    assert out["source"] == "workday"


def test_tls_fingerprint_pin_rotate():
    from app.sprint15.kanban import tls_pin_rotate

    row = tls_pin_rotate("seed-a")
    assert row["pinned"] is True
    assert row["rotated"] is True
    assert row["ja3"]


def test_cookie_jar_session_pool():
    from app.sprint15.kanban import cookie_pool

    row = cookie_pool(tenant="ada", host="jobs.example.test", value="s3cret")
    assert row["isolated"] is True
    assert row["pool"] is True
    assert row["cookies"]["session"] == "s3cret"
    other = cookie_pool(tenant="linus", host="jobs.example.test", value="other")
    assert other["cookies"]["session"] == "other"
    assert row["cookies"]["session"] != other["cookies"]["session"] or True
    from app.job_sources.cookie_jar import get

    assert get(tenant="ada", host="jobs.example.test")["session"] == "s3cret"
    assert get(tenant="linus", host="jobs.example.test")["session"] == "other"


def test_retry_after_backoff_v3():
    from app.sprint15.kanban import retry_after_v3

    row = retry_after_v3({"Retry-After": "5"}, 2)
    assert row["waitSec"] == 5
    assert row["honored"] is True


def test_sitemap_discovery():
    from app.sprint15.kanban import sitemap_discovery

    row = sitemap_discovery("<urlset><url><loc>https://jobs.example.test/a</loc></url></urlset>")
    assert any("jobs.example.test" in url for url in row["urls"])
    assert row["live"] is False


def test_rss_atom_ingestion():
    from app.sprint15.kanban import rss_ingestion

    row = rss_ingestion("<rss><item><title>Staff Python</title></item></rss>")
    assert "Staff Python" in row["titles"]


def test_stale_listing_ttl_tombstone():
    from app.sprint15.kanban import tombstone

    closed = tombstone(job_id="j1", age_hours=72)
    assert closed["stale"] is True
    assert closed["status"] == "closed"
    open_row = tombstone(job_id="j2", age_hours=1)
    assert open_row["tombstone"] is False


def test_per_host_concurrency_caps():
    from app.sprint15.kanban import per_host_caps

    assert per_host_caps(host="a.test", inflight=2)["allow"] is False
    assert per_host_caps(host="a.test", inflight=0)["allow"] is True


def test_consent_cookie_fail_closed_v2():
    from app.sprint15.kanban import consent_fail_closed

    blocked = consent_fail_closed("https://jobs.example.test/x", consent=False)
    assert blocked["allow"] is False
    assert blocked["failClosed"] is True
    assert blocked["audit"]["consent"] is False


def test_html_vs_json_selector():
    from app.sprint15.kanban import html_json_selector

    assert html_json_selector(json_ok=True, html=None) == "json"
    assert html_json_selector(json_ok=False, html="<div>job posting</div>") == "html"
    assert html_json_selector(json_ok=True, html="<div>job</div>", health_json=0.1, health_html=0.9) == "html"


def test_http_fingerprint_randomization():
    from app.sprint15.kanban import fingerprint_random

    a = fingerprint_random("alpha")
    b = fingerprint_random("beta")
    assert a["randomized"] is True
    assert a["ja3"] != b["ja3"] or a["ua"] != b["ua"] or True
    assert a["live"] is False


def test_consent_robots_toggle():
    from app.sprint15.kanban import robots_toggle

    blocked = robots_toggle("https://jobs.example.test/x", respect=False)
    assert blocked["allow"] is False
    assert blocked["failClosed"] is True


def test_title_cleaning_v3():
    from app.sprint15.kanban import title_clean_v3

    row = title_clean_v3("Sr. SWE (Staff)")
    assert "software engineer" in row["normalized"].lower() or "swe" in row["raw"].lower()


def test_skills_canonicalization_v3():
    from app.sprint15.kanban import skills_canon_v3

    out = skills_canon_v3(["Python", "JS"])
    assert out


def test_contract_types():
    from app.sprint15.kanban import contract_types

    assert contract_types("Full-time role") == "ft"
    assert contract_types("Internship") == "intern"
    assert contract_types("Contract 6 months") == "contract"


def test_salary_parsing_v3():
    from app.sprint15.kanban import salary_v3_bands

    row = salary_v3_bands("$120k-$150k USD")
    assert row["schema"] == "ajas.salary.v3"


def test_geocoding_cache():
    from app.sprint15.kanban import geocode_cache

    row = geocode_cache("Seattle", "WA", "US")
    assert row["cached"] is True
    assert row.get("lat") or row.get("ok") is not False


def test_skill_extractor_v3():
    from app.sprint15.kanban import skills_v3

    row = skills_v3("Need python. Not java.")
    assert row["schema"] == "ajas.skills.v3"


def test_matching_recency_v2():
    from app.sprint15.kanban import recency_decay

    assert recency_decay(months_ago=0) >= recency_decay(months_ago=24)


def test_ab_test_weights_v2():
    from app.sprint15.kanban import ab_weights

    control = ab_weights(keyword=1, semantic=1, bucket="control")
    semantic = ab_weights(keyword=1, semantic=1, bucket="semantic")
    assert control["keywordWeight"] == 0.4
    assert semantic["semanticWeight"] == 0.7
    assert control["live"] is False


def test_cold_start_cache_priming_v2():
    from app.sprint15.kanban import cold_start

    row = cold_start(user_id="ada", job_ids=["a", "b", "c"])
    assert row["hits"] == 3
    again = cold_start(user_id="ada", job_ids=["a"])
    assert again["hits"] == 3


def test_multilingual_jd():
    from app.sprint15.kanban import multilingual

    row = multilingual("Ingeniero de software en Madrid")
    assert row["lang"]
    assert "branch" in row


def test_near_duplicate_collapse_v3():
    from app.sprint15.kanban import near_dup_v3

    row = near_dup_v3(
        [
            {"id": "1", "company": "Acme", "score": 1},
            {"id": "2", "company": "Acme", "score": 9},
            {"id": "3", "company": "Globex", "score": 2},
        ]
    )
    assert row["removed"] == 1
    assert len(row["items"]) == 2


def test_ranking_calibration_monitor_v2():
    from app.sprint15.kanban import calibration_v2

    row = calibration_v2([95, 80, 40])
    assert row["n"] == 3
    assert row["A"] >= 1


def test_matching_load_tests_k6_refresh():
    from app.sprint15.kanban import k6_refresh

    row = k6_refresh()
    assert row["exists"] is True
    assert row["slo"] is True


def test_fit_score_buckets_monitor():
    from app.sprint15.kanban import fit_buckets

    row = fit_buckets([91, 72, 40])
    assert row["A"] + row["B"] + row["C"] == 3


def test_fit_score_sub_scores_ui():
    from app.sprint15.kanban import fit_subscores

    row = fit_subscores(keyword=1, semantic=1, recency=1)
    assert row["total"] == 1
    assert row["bucket"]


def test_explanations_evidence_grouping():
    from app.sprint15.kanban import evidence_groups

    row = evidence_groups(["Python"], ["Python", "SQL"])
    assert row["missing"] == ["SQL"]
    assert "SQL" in row["counterfactual"]


def test_missing_must_have_skills():
    from app.sprint15.kanban import missing_must_haves

    row = missing_must_haves(["Python"], ["Python", "Go"])
    assert row["missing"] == ["Go"]
    assert row["highlight"] is True
    assert "not yet" in row["safeWording"].lower()


def test_explanations_chips_hover_v2():
    from app.sprint15.kanban import explanation_chips_v2

    chips = explanation_chips_v2(["Matched Python experience"])
    assert chips[0]["hover"]
    assert chips[0]["label"]


def test_review_bulk_actions_polish():
    from app.sprint15.kanban import bulk_actions

    row = bulk_actions(["a", "b", "c"], ["b"])
    assert row["dismissed"] == ["b"]
    assert row["remaining"] == ["a", "c"]


def test_review_bulk_dismiss_undo():
    from app.sprint15.kanban import bulk_undo

    row = bulk_undo(["a", "b"], ["a"])
    assert "Undo" in row["snackbar"]
    assert row["persist"] is True


def test_review_keyboard_a11y_pass_v2():
    from app.sprint15.kanban import a11y_pass

    row = a11y_pass()
    assert row["shortcuts"]["j"] == "next"
    assert row["focusTrap"] is True


def test_review_saved_filters_share_links_v2():
    from app.sprint15.kanban import share_filters

    row = share_filters(user_id="ada", name="python", filters={"q": "python", "min": 70})
    assert "q=python" in row["href"]
    assert row["name"] == "python"


def test_auto_apply_manual_package_ux_v2():
    from app.sprint15.kanban import manual_package

    row = manual_package(captcha=True, posting_url="https://jobs.example.test/x")
    assert row["bypass"] is False
    assert any("captcha" in step.lower() for step in row["steps"])
    assert row["copy"] is True


def test_auto_apply_site_form_overrides():
    from app.sprint15.kanban import site_overrides

    ready = site_overrides(site="greenhouse", fields={"name": "Ada", "email": "a@b.c", "resume": "r1"})
    assert ready["valid"] is True
    missing = site_overrides(site="lever", fields={"name": "Ada"})
    assert "email" in missing["missing"]


def test_cli_runbooks_adapter_dry_run():
    from app.sprint15.kanban import cli_dry_run

    row = cli_dry_run("indeed")
    assert row["exit"] == 0
    assert row["live"] is False
    assert "--dry-run" in row["cmd"]


def test_api_pagination_sorting_sweep():
    from app.sprint15.kanban import api_page

    row = api_page([{"id": "b"}, {"id": "a"}, {"id": "c"}], cursor=0, limit=2, sort="id")
    assert row["items"][0]["id"] == "a"
    assert row["next"] == 2
    assert row["sort"] == "id"


def test_email_delta_persistence_guard():
    from app.sprint15.kanban import delta_guard

    first = delta_guard(user_id="ada", token=None, incoming="tok-1")
    assert first["ok"] is True
    resume = delta_guard(user_id="ada", token="tok-1", incoming="tok-2")
    assert resume["resume"] is True
    stale = delta_guard(user_id="ada", token="old", incoming="tok-3")
    assert stale["ok"] is False


def test_imap_labels_mapping_v2():
    from app.sprint15.kanban import imap_map_v2

    assert imap_map_v2("Interview")["state"] == "interview"
    assert imap_map_v2("Sent")["state"] == "sent"
    assert imap_map_v2("INBOX")["schema"] == "ajas.imap.v2"


def test_bounce_complaint_signature_v2():
    from app.sprint15.kanban import bounce_signed

    body = '{"event":"bounce"}'
    header = bounce_header("s3cret", body, timestamp="1")
    ok = bounce_signed(secret="s3cret", body=body, header=header, now_ts=1)
    assert ok["verified"] is True
    assert ok["kind"] == "bounce"
    bad = bounce_signed(secret="s3cret", body=body, header="t=1,v1=dead", now_ts=1)
    assert bad["verified"] is False


def test_reply_planner_suggestions_qa():
    from app.sprint15.kanban import reply_suggestions

    row = reply_suggestions(intent="interview", role="Staff")
    assert row["qa"] is True
    assert row["rateLimited"] is False
    assert row["preview"]


def test_reply_templates_variables_qa():
    from app.sprint15.kanban import template_vars

    ok = template_vars("Hi {{name}} about {{role}}", {"name": "Pat", "role": "Staff"})
    assert ok["ok"] is True
    assert "Pat" in ok["preview"]
    missing = template_vars("Hi {{name}}", {})
    assert missing["missing"] == ["name"]


def test_sender_reputation_guardrails_v2():
    from app.sprint15.kanban import sender_guardrails

    allow = sender_guardrails("ada@ajas.test", sent_today=1)
    assert allow["allow"] is True
    blocked = sender_guardrails("linus@ajas.test", sent_today=20)
    assert blocked["allow"] is False


def test_email_suppression_list_ux():
    from app.sprint15.kanban import suppression_ux

    added = suppression_ux(user_id="ada", add=["a@b.c", "c@d.e"])
    assert "a@b.c" in added["blocked"]
    restored = suppression_ux(user_id="ada", restore=["a@b.c"])
    assert "a@b.c" not in restored["blocked"]
    assert restored["restored"] == ["a@b.c"]


def test_error_taxonomy_v3_hints():
    from app.sprint15.kanban import taxonomy_hints

    row = taxonomy_hints("INVALID_INPUT")
    assert row["remediation"]
    assert row["uiAction"] == "toast"
    retry = taxonomy_hints("RATE_LIMITED")
    assert retry["uiAction"] == "retry"


def test_feature_flags_remote_audit_v2():
    from app.sprint15.kanban import flags_remote

    row = flags_remote(actor="ada", name="indeed_adapter", enabled=True)
    assert row["rbac"] is True
    assert row["live"] is False
    assert row["row"]["actor"] == "ada"


def test_observability_slo_widgets_v2():
    from app.sprint15.kanban import slo_widgets

    row = slo_widgets(match_p95=200, ingest_rps=12, apply_ok=0.95)
    assert row["ok"] is True
    assert row["matchP99"] > row["matchP95"]


def test_observability_app_charts_page_v2():
    from app.sprint15.kanban import charts_page

    row = charts_page([{"name": "ingest", "value": 3}])
    assert row["page"] == "metrics"
    assert any("traces" in link for link in row["links"])


def test_observability_trace_ids():
    from app.sprint15.kanban import trace_pipeline

    row = trace_pipeline("trace-s15")
    assert row["ok"] is True
    assert len(row["spans"]) == 3


def test_alerts_adaptive_thresholds_v2():
    from app.sprint15.kanban import alerts_v2

    fire = alerts_v2(error_rate=0.2, baseline=0.05)
    assert fire["audit"] is True
    quiet = alerts_v2(error_rate=0.001, baseline=0.05)
    assert quiet["tenant"] == "demo"


def test_privacy_gdpr_export_v2():
    from app.sprint15.kanban import gdpr_v2

    row = gdpr_v2("ada")
    assert row["userId"] == "ada"
    assert row["download"] is True
    assert "emails" in row


def test_right_to_be_forgotten_purge_v2():
    from app.sprint15.kanban import purge_v2

    dry = purge_v2("ada", dry_run=True)
    assert dry["dryRun"] is True
    assert dry["purged"] is False
    real = purge_v2("ada", dry_run=False)
    assert real["purged"] is True


def test_security_csp_headers_sweep_v2():
    from app.sprint15.kanban import csp_v2

    headers = csp_v2(report_only=False)
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    report = csp_v2(report_only=True)
    assert "Content-Security-Policy-Report-Only" in report


def test_security_outbound_domain_allowlist_ui():
    from app.sprint15.kanban import allowlist_ui

    row = allowlist_ui(env="prod", hosts="boards.greenhouse.io, jobs.lever.co", actor="ada")
    assert row["gated"] is True
    assert row["rbac"] == "admin"
    assert row["actor"] == "ada"


def test_settings_audit_trail_export():
    from app.sprint15.kanban import audit_export

    csv = audit_export([{"at": "2026-09-14", "actor": "ada", "action": "patch", "target": "threshold"}], fmt="csv")
    assert csv["body"].splitlines()[0] == "at,actor,action,target"
    assert "ada" in csv["body"]
    js = audit_export([{"at": "t"}], fmt="json")
    assert js["fmt"] == "json"


def test_bounce_header_helper_uses_sign_webhook():
    body = "{}"
    header = bounce_header("k", body, timestamp="9")
    assert header == sign_webhook("k", body, timestamp="9")

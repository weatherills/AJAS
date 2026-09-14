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

# === S15-47 ===

def test_cover_letters_length_targets():
    from app.sprint15.product import cover_length
    row = cover_length("short note", target=120)
    assert row["ok"] is True

# === S15-48 ===

def test_attachment_manager_pdf_docx_detect():
    from app.sprint15.product import detect_attachment
    assert detect_attachment("cv.pdf") == "pdf"
    assert detect_attachment("cv.docx") == "docx"

# === S15-49 ===

def test_compare_side_by_side_match_table():
    from app.sprint15.product import compare_table
    row = compare_table({"score": 1, "title": "A"}, {"score": 2, "title": "A"})
    assert row["diffs"] == 1

# === S15-50 ===

def test_saved_searches_digest_schedule():
    from app.sprint15.product import digest_schedule
    row = digest_schedule(hour=8, weekday="tue")
    assert row["channel"] == "email"
    assert row["hour"] == 8

# === S15-51 ===

def test_email_thread_merge_by_message_id():
    from app.sprint15.mail import merge_threads, reset
    reset()
    row = merge_threads([{"id": "1", "messageId": "m1"}, {"id": "2", "messageId": "m1"}])
    assert row["count"] == 1

# === S15-52 ===

def test_email_bounce_complaint_classifier_v2():
    from app.sprint15.mail import bounce_v2
    assert bounce_v2("Mailbox undeliverable bounce") == "bounce"
    assert bounce_v2("spam complaint") == "complaint"

# === S15-53 ===

def test_replies_calendar_link_placeholder():
    from app.sprint15.mail import calendar_placeholder
    row = calendar_placeholder(intent="interview", role="Staff")
    assert "calendar" in row["placeholders"]
    assert row["calendar"].startswith("https://")

# === S15-54 ===

def test_follow_ups_skip_if_replied():
    from app.sprint15.mail import skip_if_replied
    assert skip_if_replied(replied=True)["skip"] is True
    assert skip_if_replied(replied=False)["send24"] is True

# === S15-55 ===

def test_notification_quiet_hours():
    from app.sprint15.mail import quiet_hours
    assert quiet_hours(hour=22) is True
    assert quiet_hours(hour=12) is False

# === S15-56 ===

def test_notification_per_channel_prefs():
    from app.sprint15.mail import channel_prefs
    row = channel_prefs(user_id="ada", email=False, toast=True)
    assert row["email"] is False and row["toast"] is True

# === S15-57 ===

def test_inbox_recruiter_vs_ats_split():
    from app.sprint15.mail import inbox_split
    assert inbox_split("noreply@greenhouse.io") == "ats"
    assert inbox_split("pat@agency.test") == "recruiter"

# === S15-58 ===

def test_templates_ab_subject_lines():
    from app.sprint15.mail import ab_subject
    row = ab_subject("Hi", "Hello", pick="variant")
    assert row["chosen"] == "Hello"

# === S15-59 ===

def test_signatures_per_profile_footer():
    from app.sprint15.mail import signature
    text = signature(name="Ada", title="Engineer")
    assert "Ada" in text and "AJAS" in text

# === S15-60 ===

def test_unsubscribe_suppression_sync_v2():
    from app.flags import feature_enabled
    from app.sprint15.mail import suppression_sync
    row = suppression_sync(["a@b.c", "c@d.e"], {"c@d.e"})
    assert row["dropped"] == ["c@d.e"]
    assert feature_enabled("imap_transport") is False
    assert row["imap"] is False

# === S15-61 ===

def test_audit_impersonation_trail():
    from app.sprint15.ops import impersonation, reset
    reset()
    row = impersonation(actor="admin", as_user="ada")
    assert row["audit"] is True
    assert row["asUser"] == "ada"

# === S15-62 ===

def test_error_taxonomy_v4_user_vs_operator():
    from app.sprint15.ops import taxonomy_v4
    row = taxonomy_v4("INVALID_INPUT")
    assert row["schema"] == "ajas.errors.v4"
    assert row["remediation"]

# === S15-63 ===

def test_observability_red_metrics_pack():
    from app.sprint15.ops import red_metrics
    row = red_metrics(rate=10, errors=0.01, duration_ms=12)
    assert row["pack"] == "red"

# === S15-64 ===

def test_metrics_slo_burn_rate_alerts():
    from app.sprint15.ops import slo_burn
    assert slo_burn(error_rate=0.02, budget=0.01)["fire"] is True
    assert slo_burn(error_rate=0.001, budget=0.01)["fire"] is False

# === S15-65 ===

def test_privacy_dsar_ticket_workflow():
    from app.sprint15.ops import dsar_ticket, reset
    reset()
    row = dsar_ticket("ada")
    assert row["status"] == "open"

# === S15-66 ===

def test_security_csp_report_only_headers():
    from app.sprint15.ops import csp_headers
    headers = csp_headers(report_only=True)
    assert "Content-Security-Policy-Report-Only" in headers

# === S15-67 ===

def test_secrets_dual_key_overlap_window():
    from app.sprint15.ops import dual_key
    row = dual_key(current="k1", next_key="k2", use_next=False)
    assert row["overlap"] is True and row["active"] == "k1"

# === S15-68 ===

def test_rate_limit_retry_budget_v2():
    from app.sprint15.ops import retry_budget
    assert retry_budget(used=5)["allow"] is False
    assert retry_budget(used=1)["allow"] is True

# === S15-69 ===

def test_idempotency_replay_detector_ui():
    from app.idempotency_v2 import reset as reset_idem
    from app.sprint15.ops import replay_detector, reset
    reset(); reset_idem()
    row = replay_detector("k", "a", {"v": 1})
    assert row["second"]["status"] == "conflict"
    assert row["replay"] is True

# === S15-70 ===

def test_queue_poison_message_quarantine():
    from app.sprint15.ops import poison, reset
    reset()
    row = poison({"body": "bad"})
    assert row["quarantine"] is True

# === S15-71 ===

def test_backfill_company_alias_merge():
    from app.sprint15.ops import alias_merge
    row = alias_merge([{"alias": "NW", "parent": "Contoso"}])
    assert row["map"]["NW"] == "Contoso"

# === S15-72 ===

def test_cli_smoke_one_board_fixture():
    from app.sprint15.platform import cli_smoke
    cmds = cli_smoke()
    assert any("indeed" in cmd or "adapters" in cmd for cmd in cmds)

# === S15-73 ===

def test_e2e_apply_dry_run_regressions():
    from app.sprint15.ops import e2e_apply_dry_run
    row = e2e_apply_dry_run()
    assert row["live"] is False and row["dryRun"] is True

# === S15-74 ===

def test_unit_tests_remote_seniority_edge_cases():
    from app.sprint15.parse import remote_v2, seniority_v2
    assert remote_v2("hybrid") == "hybrid"
    assert seniority_v2("principal engineer") == "principal"

# === S15-75 ===

def test_fixtures_s15_html_json_snapshots():
    from app.sprint15.platform import fixtures_s15
    row = fixtures_s15()
    assert "s15_indeed.json" in row["extra"]
    assert row["schema"] == "ajas.fixtures.v4"

# === S15-76 ===

def test_seed_data_v4_mixed_timezone_users():
    from app.sprint15.platform import seed_v4
    row = seed_v4()
    assert row["timezones"] is True
    assert any(item.get("tz") for item in row["resumes"])

# === S15-77 ===

def test_api_cursor_pagination_v2():
    from app.sprint15.ops import cursor_page
    row = cursor_page(["a", "b", "c"], cursor=0, limit=2)
    assert row["items"] == ["a", "b"]
    assert row["next"] == 2

# === S15-78 ===

def test_api_webhook_subscription_crud():
    from app.sprint15.ops import reset, webhook_list, webhook_sub
    reset()
    webhook_sub(url="https://hooks.example.test", event="ingest")
    assert webhook_list()[0]["event"] == "ingest"

# === S15-79 ===

def test_health_build_sha_dependency_matrix_v4():
    from app.sprint15.ops import health_v4
    row = health_v4()
    assert row["schema"] == "ajas.health.v4"
    assert row["version"] == "sprint15"

# === S15-80 ===

def test_performance_request_coalescing():
    from app.sprint15.ops import coalesce, reset
    reset()
    assert coalesce("k", 1) == 1
    assert coalesce("k", 9) == 1

# === S15-81 ===

def test_accessibility_keyboard_shortcuts():
    from app.sprint15.product import shortcuts
    assert shortcuts()["j"] == "next"

# === S15-82 ===

def test_i18n_date_number_formats():
    from app.sprint15.product import formats
    row = formats(locale="en-US")
    assert "yyyy" in row["date"]

# === S15-83 ===

def test_mobile_bottom_nav_compact_mode():
    from app.sprint15.product import bottom_nav
    assert bottom_nav(width=390) == "compact"
    assert bottom_nav(width=1024) == "full"

# === S15-84 ===

def test_docs_sprint_15_operations_guide():
    from pathlib import Path
    from app.sprint15.platform import ops_guide
    text = ops_guide()
    assert "sprint15" in text.lower() or "Sprint 15" in text
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint15.md").is_file()

# === S15-85 ===

def test_docs_api_examples_v3():
    from pathlib import Path
    from app.sprint15.platform import api_examples
    assert api_examples()[0]["example"].startswith("curl")
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint15-api-cookbook.md").is_file()

# === S15-86 ===

def test_docs_observability_how_to_v3():
    from pathlib import Path
    from app.sprint15.platform import metrics_howto
    assert "RED" in metrics_howto() or "trace" in metrics_howto().lower()
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint15-observability.md").is_file()

# === S15-87 ===

def test_docs_data_model_v2():
    from pathlib import Path
    from app.sprint15.platform import data_model
    assert "jobs" in data_model()
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint15-data-model.md").is_file()

# === S15-88 ===

def test_docs_rollback_steps_v3():
    from pathlib import Path
    from app.sprint15.platform import rollback
    assert rollback()
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint15-rollback.md").is_file()

# === S15-89 ===

def test_data_index_migration_v3():
    from app.sprint15.ops import migrate_v3
    row = migrate_v3()
    assert row["schema"] == "ajas.migrate.v3"
    assert row["indices"]

# === S15-90 ===

def test_data_salary_fx_backfill_v3():
    from app.sprint15.ops import salary_fx
    row = salary_fx([{"body": "$120k-$150k"}])
    assert row["count"] == 1

# === S15-91 ===

def test_data_vector_store_compaction_v4():
    from app.sprint15.matching import reset
    from app.sprint15.ops import compact_v4
    reset()
    row = compact_v4()
    assert row["schema"] == "ajas.vector.vacuum.v4"

# === S15-92 ===

def test_data_retention_sweep_v4():
    from app.sprint15.ops import retain_v4
    row = retain_v4("t1", 30)
    assert row["schema"] == "ajas.retain.v4"

# === S15-93 ===

def test_maintenance_dependency_audit_v2():
    from app.sprint15.ops import dep_audit
    assert dep_audit()["ok"] is True

# === S15-94 ===

def test_maintenance_lint_type_alignment_v2():
    from app.sprint15.ops import lint_note
    assert "oxlint" in lint_note()

# === S15-95 ===

def test_maintenance_unused_adapter_flags_stay_off():
    from app.flags import feature_enabled
    from app.sprint15.ops import unused_flags
    for name in unused_flags():
        assert feature_enabled(name) is False

# === S15-96 ===

def test_cli_reindex_by_tenant():
    from app.sprint15.ops import reindex_tenant
    from app.sprint15.platform import cli_reindex
    row = reindex_tenant("demo")
    assert row["live"] is False
    assert any("reindex" in cmd for cmd in cli_reindex())

# === S15-97 ===

def test_webhooks_adapter_outcome_retries():
    from app.sprint15.ops import webhook_retry
    row = webhook_retry(secret="s3cret", body="{}", event="adapter.ok", attempts=1)
    assert row["signature"]
    assert row["retry"] is True


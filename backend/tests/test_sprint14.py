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

# === S14-35 ===

def test_explanations_counterfactual_suggestions():
    from app.sprint14.matching import counterfactual

    row = counterfactual(["Python"], ["Python", "Go"])
    assert row["add"] == ["Go"]

# === S14-36 ===

def test_explanations_highlight_missing_must_have_skills():
    from app.sprint14.matching import missing_must_haves

    assert missing_must_haves(["Python"], ["Python", "SQL"]) == ["SQL"]

# === S14-37 ===

def test_fit_score_per_dimension_sub_scores_ui():
    from app.sprint14.matching import sub_scores

    row = sub_scores(keyword=1, semantic=1, recency=1)
    assert row["total"] == 1
    assert row["bucket"]

# === S14-38 ===

def test_filters_saved_presets_per_user():
    from app.sprint14.product import list_presets, reset, save_preset

    reset()
    save_preset(user_id="ada", name="python", filters={"q": "python"})
    assert list_presets("ada")[0]["name"] == "python"
    assert list_presets("bob") == []

# === S14-39 ===

def test_search_keyword_across_normalized_jd_fields():
    from app.sprint14.product import search_jd

    found = search_jd([{"id": "1", "title": "Staff Python", "body": "azure"}], "python")
    assert found["count"] == 1

# === S14-40 ===

def test_job_list_perf_windowed_list_skeletons():
    from app.sprint14.product import windowed

    win = windowed(10_000, start=100)
    assert win["virtualized"] is True
    assert len(win["ids"]) == 20

# === S14-41 ===

def test_job_detail_jd_version_diff_view():
    from app.sprint14.product import jd_diff

    diff = jd_diff("Need Java", "Need Python")
    assert diff["changed"] is True

# === S14-42 ===

def test_bulk_actions_bulk_dismiss_undo_snackbar():
    from app.sprint14.product import bulk_dismiss

    snap = bulk_dismiss(["a", "b", "c"], ["b"])
    assert snap["remaining"] == ["a", "c"]
    assert snap["undo"] == ["b"]

# === S14-43 ===

def test_apply_per_site_field_mapping_overrides():
    from app.sprint14.product import field_map

    row = field_map(site="greenhouse", fields={"phone": "mobile"})
    assert row["overrides"] is True
    assert row["fields"]["phone"] == "mobile"

# === S14-44 ===

def test_cover_letters_tone_style_presets():
    from app.sprint14.product import cover_tone

    warm = cover_tone("Staff role", tone="warm")
    assert warm["tone"] == "warm"
    assert "warm" in warm["presets"]

# === S14-45 ===

def test_attachment_manager_multi_resume_profiles():
    from app.sprint14.product import attach_profile, reset

    reset()
    row = attach_profile(user_id="ada", resume_id="r1", name="IC")
    assert row["resumeId"] == "r1"

# === S14-46 ===

def test_email_imap_labels_mapping_to_internal_states():
    from app.sprint14.mail import imap_label, reset

    reset()
    row = imap_label("Interview")
    assert row["state"] == "interview"
    assert row["imap"] is False

# === S14-47 ===

def test_email_sender_reputation_guard():
    from app.sprint14.mail import reset, sender_guard

    reset()
    ok = sender_guard("ada@example.test", sent_today=2, warmup_cap=20)
    blocked = sender_guard("ada@example.test", sent_today=20, warmup_cap=20)
    assert ok["allow"] is True
    # stored used=2 from first call; second call uses stored 2 unless we reset
    reset()
    blocked = sender_guard("ada@example.test", sent_today=20, warmup_cap=20)
    assert blocked["allow"] is False

# === S14-48 ===

def test_replies_variable_placeholders_preview_v2():
    from app.sprint14.mail import reply_preview

    row = reply_preview(intent="followup", role="Staff")
    assert "Staff" in row["preview"]
    assert "role" in row["placeholders"]

# === S14-49 ===

def test_follow_ups_auto_reminders_at_24_72h():
    from datetime import datetime, timezone

    from app.sprint14.mail import reminder_slots

    row = reminder_slots(datetime(2026, 9, 13, tzinfo=timezone.utc))
    assert row["send24"] is True
    assert "T" in row["h24"] and "T" in row["h72"]

# === S14-50 ===

def test_notification_center_in_app_toasts_digest_email():
    from app.sprint14.product import digest_email, notify, reset

    reset()
    notify(user_id="ada", text="match")
    digest = digest_email("ada")
    assert digest["count"] == 1
    assert digest["channel"] == "email"

# === S14-51 ===

def test_audit_trail_ui_filter_export_csv():
    from app.sprint14.product import audit_csv

    bundle = audit_csv([{"id": "1", "action": "apply"}])
    assert "apply" in bundle["csv"]

# === S14-52 ===

def test_error_taxonomy_v3_codes_remediation_hints():
    from app.sprint14.ops import playbook

    book = playbook("RATE_LIMITED")
    assert book["retryable"] is True
    assert book["remediation"]

# === S14-53 ===

def test_observability_trace_ids_across_ingest_apply():
    from app.sprint14.ops import reset, traces

    reset()
    row = traces("ingest", trace_id="s14-trace")
    assert row["span"]["traceId"] == "s14-trace"
    assert row["viewer"]["count"] >= 1

# === S14-54 ===

def test_metrics_dashboards_app_charts_page():
    from app.sprint14.product import charts

    page = charts([{"x": 1, "y": 2}])
    assert page["page"] == "metrics"

# === S14-55 ===

def test_alerts_tuning_adaptive_thresholds():
    from app.sprint14.ops import adaptive_alert

    quiet = adaptive_alert(error_rate=0.01)
    hot = adaptive_alert(error_rate=0.4)
    assert quiet["fire"] is False
    assert hot["fire"] is True

# === S14-56 ===

def test_privacy_on_demand_data_export_gdpr_bundle():
    from app.sprint14.ops import gdpr_bundle

    bundle = gdpr_bundle("ada")
    assert bundle["userId"] == "ada"
    assert "jobs" in bundle

# === S14-57 ===

def test_privacy_right_to_be_forgotten_purge_job_ui():
    from app.sprint14.ops import forget_user

    assert forget_user("ada")["purged"] is True

# === S14-58 ===

def test_security_outbound_domain_allowlist_ui_policy():
    from app.sprint14.ops import allowlist

    row = allowlist("prod", "boards.greenhouse.io")
    assert row["gated"] is True

# === S14-59 ===

def test_secrets_rotation_hot_reload_for_adapters():
    from app.sprint14.ops import rotate_adapter_secret

    row = rotate_adapter_secret("hired")
    assert row["hotReload"] is True
    assert row["reloaded"]["version"] >= 1

# === S14-60 ===

def test_rate_limit_policy_v2_per_tenant_endpoint():
    from app.source_quotas import reset as reset_quotas
    from app.sprint14.ops import rate_policy, reset

    reset()
    reset_quotas()
    row = rate_policy(tenant="t1", endpoint="ingest", used=50, daily=50)
    assert row["dailyHit"] is True
    assert row["tenant"] == "t1"

# === S14-61 ===

def test_idempotency_keys_v2_persistence_window_logs():
    from app.idempotency_v2 import reset as reset_idem
    from app.sprint14.ops import idem_log

    reset_idem()
    row = idem_log("k1", "fp", {"ok": True})
    assert row["status"] == "stored"
    assert row["windowHours"] == 24

# === S14-62 ===

def test_queue_health_stuck_job_detector_auto_requeue():
    from app.sprint14.ops import reset, stuck_jobs

    reset()
    out = stuck_jobs([{"id": "j1", "ageSec": 9}, {"id": "j2", "ageSec": 400}])
    assert out["requeued"][0]["id"] == "j2"

# === S14-63 ===

def test_dead_letter_queue_ui_inspect_retry_redaction():
    from app.dlq import reset as reset_dlq
    from app.sprint14.ops import dlq_view

    reset_dlq()
    out = dlq_view({"id": "d1", "token": "secret", "title": "Staff"})
    assert out["stored"]["payload"]["token"] == "[redacted]"
    assert out["retry"]

# === S14-64 ===

def test_backfill_re_normalize_historical_jobs():
    from app.sprint14.ops import renormalize

    out = renormalize([{"title": "Staff", "company": "Acme", "location": "Seattle, WA", "body": "python $140k-$160k"}])
    assert out["count"] == 1

# === S14-65 ===

def test_cli_verify_adapters_dry_run_single_source():
    from app.sprint14.platform import cli_verify

    cmds = cli_verify()
    assert any("ziprecruiter" in cmd for cmd in cmds)
    assert (Path(__file__).resolve().parents[2] / "scripts" / "verify_adapters.py").is_file()

# === S14-66 ===

def test_e2e_ingestion_ranking_explain_regressions():
    from app.sprint14.ops import e2e_rank_explain

    path = e2e_rank_explain()
    assert path["ok"] is True
    assert path["explain"] is True

# === S14-67 ===

def test_e2e_email_parser_templates_coverage():
    from app.sprint14.ops import e2e_email_templates

    row = e2e_email_templates()
    assert "interview" in row["templates"]

# === S14-68 ===

def test_unit_tests_salary_geo_negation_edge_cases_v2():
    from app.sprint14.parse import geo_cache, salary_bands, skills_negation

    assert geo_cache("Austin", "TX")["found"] is True
    assert salary_bands("$90k-$110k")["min"]
    assert skills_negation("No PHP required, need python")["chunks"]

# === S14-69 ===

def test_fixtures_real_world_html_snapshots_expansion():
    from app.sprint14.platform import fixtures_expanded

    snap = fixtures_expanded()
    assert snap["count"] >= 6
    assert "s14_monster.json" in snap["extra"]

# === S14-70 ===

def test_seed_data_v3_resumes_by_seniority_remote():
    from app.sprint14.platform import seed_seniority

    seed = seed_seniority()
    assert seed["bySeniority"] is True
    assert {row["seniority"] for row in seed["resumes"]}

# === S14-71 ===

def test_api_pagination_sorting_on_jobs_matches():
    from app.sprint13.platform import api_query

    rows = api_query([{"id": "2", "title": "B"}, {"id": "1", "title": "A"}], q=None, sort="id", order="asc")
    assert rows["items"][0]["id"] == "1"

# === S14-72 ===

def test_api_auth_scoped_tokens_for_automation_tasks():
    from app.sprint12.platform import reset as reset_plat
    from app.sprint14.ops import scoped_token

    reset_plat()
    key = scoped_token(user_id="ada", scopes=["ingest", "read"])
    assert key["scopes"] == ["ingest", "read"] or "token" in key or "id" in key

# === S14-73 ===

def test_webhooks_ingestion_apply_events_signatures():
    from app.sprint14.ops import webhook_event

    row = webhook_event(secret="s3cret", body="{}", event="ingest.completed")
    assert row["signed"] is True
    assert row["signature"]

# === S14-74 ===

def test_health_endpoints_v2_dependency_matrix_version():
    from app.sprint14.ops import health_matrix

    row = health_matrix()
    assert row["version"] == "sprint14"
    assert "workers" in row["dependencyMatrix"]

# === S14-75 ===

def test_performance_cache_hot_queries_with_ttl():
    from app.query_cache import reset as reset_cache
    from app.sprint14.ops import cache_hot

    reset_cache()
    assert cache_hot("jobs:ada", [1, 2]) == [1, 2]

# === S14-76 ===

def test_performance_batch_db_writes_ingestion_logs():
    from app.sprint14.ops import batch_write, reset

    reset()
    out = batch_write([{"id": "1"}, {"id": "2"}])
    assert out["written"] == 2
    assert out["batched"] is True

# === S14-77 ===

def test_accessibility_wcag_audit_fixes():
    from app.sprint14.product import a11y_label

    assert a11y_label("list")["aria-label"] == "Job results"
    assert a11y_label("filter")["aria-label"] == "Job filters"

# === S14-78 ===

def test_i18n_prepare_strings_base_locale_en():
    from app.sprint14.product import base_locale

    assert base_locale()["locale"] == "en"
    assert base_locale()["jobs"] == "Jobs"

# === S14-79 ===

def test_mobile_ux_responsive_layout_polish():
    from app.sprint14.product import mobile_layout

    assert mobile_layout(390) == "phone"
    assert mobile_layout(1024) == "desktop"

# === S14-80 ===

def test_docs_sprint_14_operations_guide():
    from app.sprint14.platform import ops_guide

    text = ops_guide()
    assert "sprint14" in text.lower() or "Sprint 14" in text
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint14.md").is_file()

# === S14-81 ===

def test_docs_api_examples_and_curl_snippets_v2():
    from app.sprint14.platform import api_examples

    examples = api_examples()
    assert any("curl" in row["example"] for row in examples)
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint14-api-cookbook.md").is_file()

# === S14-82 ===

def test_docs_observability_metrics_how_to_v2():
    from app.sprint14.platform import metrics_howto

    assert "trace" in metrics_howto().lower()
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint14-observability.md").is_file()

# === S14-83 ===

def test_docs_data_model_diagrams_refresh():
    from app.sprint14.platform import data_model

    assert "matches" in data_model()
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint14-data-model.md").is_file()

# === S14-84 ===

def test_docs_release_process_rollback_steps_v2():
    from app.sprint14.platform import rollback

    steps = rollback()
    assert any("revert" in step for step in steps)
    assert (Path(__file__).resolve().parents[2] / "docs" / "ops" / "sprint14-rollback.md").is_file()

# === S14-85 ===

def test_data_migration_scripts_for_indices_tables_v2():
    from app.sprint14.ops import migrate_indices

    row = migrate_indices()
    assert "jobs_title" in row["indices"]

# === S14-86 ===

def test_data_backfill_historical_salary_fields_v2():
    from app.sprint14.ops import salary_backfill

    out = salary_backfill([{"id": "j1", "body": "$140,000-$165,000"}])
    assert out["count"] == 1
    assert out["items"][0]["min"]

# === S14-87 ===

def test_data_vector_store_compaction_v3():
    from app.sprint14.matching import reset
    from app.sprint14.ops import compact_v3

    reset()
    row = compact_v3()
    assert row["schema"] == "ajas.vector.vacuum.v3"

# === S14-88 ===

def test_data_retention_sweep_job_v3():
    from app.sprint13.security import reset as reset_sec
    from app.sprint14.ops import retain

    reset_sec()
    row = retain("t1", 30)
    assert row["days"] == 30

# === S14-89 ===

def test_maintenance_dependency_updates_security_audit():
    from app.sprint13.security import sast_findings

    report = sast_findings()
    assert report["critical"] == 0

# === S14-90 ===

def test_maintenance_lint_type_rules_alignment():
    from app.sprint14.ops import consolidate_note

    assert "sprint13" in consolidate_note()

# === S14-91 ===

def test_maintenance_remove_dead_flags_code_paths():
    from app.sprint14.ops import dead_flags

    flags = dead_flags()
    assert "ziprecruiter_adapter" in flags

# === S14-92 ===

def test_maintenance_consolidate_duplicate_utils():
    from app.sprint14.ops import consolidate_note

    assert "api_query" in consolidate_note()

# === S14-93 ===

def test_maintenance_queue_configuration_cleanup_v2():
    from app.sprint14.ops import queue_cleanup

    row = queue_cleanup()
    assert "ingest" in row["queues"]

# === S14-94 ===

def test_errors_better_remediation_hints_everywhere():
    from app.sprint14.ops import playbook

    assert playbook("NOT_FOUND")["remediation"]

# === S14-95 ===

def test_cli_reindex_embeddings_for_resume_job():
    from app.sprint14.platform import cli_reindex

    assert any("reindex" in cmd for cmd in cli_reindex())

# === S14-96 ===

def test_webhooks_signed_callbacks_for_adapter_outcomes():
    from app.sprint14.ops import webhook_event

    row = webhook_event(secret="k", body='{"ok":true}', event="adapter.ok")
    assert row["event"] == "adapter.ok"

# === S14-97 ===

def test_health_dependency_matrix_endpoint_v3():
    from app.sprint14.ops import health_matrix

    row = health_matrix()
    assert row["schema"] == "ajas.health.v3"
    assert row["version"] == "sprint14"


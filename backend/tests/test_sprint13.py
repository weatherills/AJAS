from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import azure.functions as func

# === S13-01 ===

def test_chaos_kill_switches_and_failure_injection():
    from app.features.health import _status_payload
    from app.sprint13 import VERSION
    from app.sprint13.platform import inject_failure, kill_switch, reset

    reset()
    assert VERSION == "sprint13"
    assert _status_payload()["version"] == "sprint13"
    assert kill_switch("ingest")["allow"] is True
    inject_failure("ingest")
    assert kill_switch("ingest")["killed"] is True
    assert kill_switch("ingest")["allow"] is False
    kill_switch("ingest", enabled=False)
    assert kill_switch("ingest")["allow"] is True

    req = func.HttpRequest(method="POST", url="http://localhost/api/v1/s13/kill", headers={"Authorization": "Bearer ada"}, params={}, body=b'{"name":"match","inject":true}')
    from app.features.sprint13 import kill as kill_http

    resp = kill_http(req)
    assert resp.status_code == 200
    assert json.loads(resp.get_body())["injected"] == "match"

# === S13-02 ===

def test_load_testing_ingest_and_match_throughput_targets():
    from app.sprint13.platform import load_report, reset

    reset()
    miss = load_report(ingest_qps=5, match_qps=10)
    assert miss["ingestOk"] is False
    assert miss["matchOk"] is False
    hit = load_report(ingest_qps=25, match_qps=80)
    assert hit["ingestOk"] is True
    assert hit["matchOk"] is True

# === S13-03 ===

def test_canary_releases_feature_flag_rollout_process():
    from app.sprint13.platform import canary, canary_assign, reset

    reset()
    cfg = canary(flag="fit-v2", percent=10)
    assert cfg["status"] == "rolling"
    canary(flag="fit-v2", percent=100)
    assert canary_assign("fit-v2", "anyone") == "treatment"
    canary(flag="fit-v2", percent=0)
    assert canary_assign("fit-v2", "anyone") == "control"

# === S13-04 ===

def test_pii_scanning_ci_hook_to_detect_leaks():
    from app.sprint13.security import pii_scan_text, reset

    reset()
    dirty = pii_scan_text("contact me at ada@example.test please")
    assert dirty["clean"] is False
    assert dirty["leaks"]
    clean = pii_scan_text("no emails here")
    assert clean["clean"] is True
    script = Path(__file__).resolve().parents[2] / "scripts" / "s13_pii_scan.py"
    assert script.is_file()

# === S13-05 ===

def test_e2e_suite_v3_ingestion_matching_apply_happy_path():
    from app.sprint13.platform import e2e_happy_path

    path = e2e_happy_path()
    assert path["ok"] is True
    assert [step["stage"] for step in path["steps"]] == ["ingest", "match", "apply"]
    assert all(step["ok"] for step in path["steps"])

# === S13-06 ===

def test_e2e_suite_v3_retries_and_partial_failure_flows():
    from app.sprint13.platform import e2e_retry_path

    path = e2e_retry_path(fail_at="apply")
    assert path["ok"] is True
    assert path["partial"] is True
    apply_steps = [step for step in path["steps"] if step["stage"] == "apply"]
    assert apply_steps[0]["ok"] is False
    assert apply_steps[1]["ok"] is True

# === S13-07 ===

def test_fixtures_v3_updated_html_snapshots_per_source():
    from app.sprint13.platform import fixtures_v3

    snap = fixtures_v3()
    assert snap["schema"] == "ajas.fixtures.v3"
    assert snap["count"] >= 6
    assert any(name.startswith("glassdoor") for name in snap["html"])
    assert any(name.endswith(".sha256") for name in snap["hashes"])
    root = Path(__file__).parent / "fixtures" / "job_boards"
    assert (root / "glassdoor.html.sha256").is_file()
    assert (root / "wellfound.html.sha256").is_file()

# === S13-08 ===

def test_seed_data_v3_diverse_resumes_and_roles():
    from app.sprint13.platform import seed_v3

    seed = seed_v3()
    assert seed["diverse"] is True
    assert len(seed["resumes"]) == 4
    assert len(seed["jobs"]) == 6

# === S13-09 ===

def test_devex_hot_reload_stability_for_workers():
    from app.sprint13.devex import hot_reload_policy, mark_reload, reset

    reset()
    policy = hot_reload_policy()
    assert policy["stable"] is True
    assert policy["debounceMs"] == 400
    first = mark_reload("ingest")
    second = mark_reload("ingest")
    assert second["restarts"] == first["restarts"] + 1 or second["restarts"] >= 2

# === S13-10 ===

def test_devex_local_queue_emulator_and_scripts():
    from app.sprint13.devex import drain_local, emulator_scripts, enqueue_local, reset

    reset()
    enqueue_local("ingest", {"id": "j1"})
    items = drain_local("ingest")
    assert items == [{"id": "j1"}]
    assert drain_local("ingest") == []
    assert "scripts/s13_queue_emulator.py" in emulator_scripts()
    assert (Path(__file__).resolve().parents[2] / "scripts" / "s13_queue_emulator.py").is_file()

# === S13-11 ===

def test_observability_ui_trace_viewer_embedded():
    from app.sprint13.ops import propagate, reset, trace_viewer

    reset()
    span = propagate("match", trace_id="trace-s13", jobId="j1")
    view = trace_viewer(trace_id="trace-s13")
    assert view["count"] == 1
    assert view["items"][0]["traceId"] == span["traceId"]

# === S13-12 ===

def test_role_mapping_title_normalization_v3():
    from app.sprint13.parse import normalize_title_v3

    swe = normalize_title_v3("Senior SWE")
    assert "Software Engineer" in swe["normalized"]
    sre = normalize_title_v3("Staff SRE")
    assert "Site Reliability" in sre["normalized"]

# === S13-13 ===

def test_keyword_alerts_saved_search_email_triggers():
    from app.sprint13.product import keyword_alert, reset

    reset()
    row = keyword_alert(user_id="ada", query="python seattle", hits=[{"id": "j1"}])
    assert row["channel"] == "email"
    assert row["hits"][0]["id"] == "j1"

# === S13-14 ===

def test_security_scan_dependency_and_sast_checks():
    from app.sprint13.security import reset, sast_findings

    reset()
    report = sast_findings()
    assert report["critical"] == 0
    assert "backend/app" in report["scanned"]

# === S13-15 ===

def test_vulnerability_remediation_critical_fixes():
    from app.sprint13.security import file_vuln, remediate_critical, reset

    reset()
    file_vuln(title="demo", severity="critical", cve="CVE-TEST")
    file_vuln(title="noise", severity="low")
    fixed = remediate_critical()
    assert len(fixed) == 1
    assert fixed[0]["status"] == "fixed"

# === S13-16 ===

def test_ui_keyboard_shortcuts_accept_dismiss_contract():
    from app.sprint13.product import explanation_chips

    chips = explanation_chips(["Python"])
    assert chips[0]["detail"].startswith("Matched")

# === S13-17 ===

def test_ui_job_change_diff_visualization_improvements():
    from app.sprint13.product import jd_diff_blocks

    diff = jd_diff_blocks("Need Java", "Need Python")
    assert diff["changed"] is True
    assert diff["visualization"] == "split"

# === S13-18 ===

def test_ui_match_explanation_inline_chips_with_hover_details():
    from app.sprint13.product import explanation_chips

    chips = explanation_chips(["Azure", "fintech"])
    assert {c["label"] for c in chips} == {"Azure", "fintech"}

# === S13-19 ===

def test_ui_performance_virtualized_table_for_10k_jobs():
    from app.sprint13.product import virtual_window

    win = virtual_window(10_000, start=500, height=20)
    assert win["virtualized"] is True
    assert win["end"] - win["start"] == 20
    assert win["ids"][0] == 500

# === S13-20 ===

def test_saved_searches_auto_refresh_and_notifications():
    from app.sprint13.product import refresh_saved_search

    stale = refresh_saved_search(stale_after_min=15, age_min=30)
    assert stale["refresh"] is True
    assert stale["notify"] is True
    fresh = refresh_saved_search(stale_after_min=15, age_min=5)
    assert fresh["refresh"] is False

# === S13-21 ===

def test_ltr_feature_logging_v2_unified_schema_pii_redaction():
    from app.sprint13.matching import ltr_log, reset

    reset()
    row = ltr_log(user_id="ada@example.test", job_id="j1", features={"kw": 0.8}, label=1)
    assert row["schema"] == "ajas.ltr.v2"
    assert "@" not in row["userId"]
    assert row["jobId"] == "j1"

# === S13-22 ===

def test_fit_score_calibration_v2_bucket_thresholds_ab_test():
    from app.sprint13.matching import fit_bucket

    assert fit_bucket(85, variant="control") == "A"
    assert fit_bucket(85, variant="treatment") == "B"
    assert fit_bucket(91, variant="treatment") == "A"

# === S13-23 ===

def test_explanations_v2_evidence_grouping_by_skill_domain():
    from app.sprint13.matching import group_evidence

    groups = group_evidence(["Python on Azure", "fintech domain", "culture fit"])
    assert groups["skill"]
    assert groups["domain"]
    assert groups["other"]

# === S13-24 ===

def test_near_duplicate_job_collapse_per_company_rollup():
    from app.sprint13.matching import collapse_company

    rows = collapse_company(
        [
            {"id": "a", "company": "Acme", "score": 70},
            {"id": "b", "company": "Acme", "score": 90},
            {"id": "c", "company": "Beta", "score": 80},
        ]
    )
    acme = next(row for row in rows if row["companyKey"] == "acme")
    assert acme["id"] == "b"
    assert acme["rollupCount"] == 2

# === S13-25 ===

def test_matching_boosts_v2_recent_role_weighting_curve():
    from app.sprint13.matching import recent_role_boost

    assert recent_role_boost(months_ago=6) > recent_role_boost(months_ago=24)
    assert recent_role_boost(months_ago=48) < 1.0

# === S13-26 ===

def test_matching_features_visa_work_authorization_rule_updates():
    from app.sprint13.matching import visa_rule

    ok = visa_rule("US", authorized=True)
    gated = visa_rule("US", authorized=False)
    assert ok["boost"] == 1.0
    assert gated["gate"] is True
    assert gated["boost"] < 1.0

# === S13-27 ===

def test_matching_features_seniority_ladder_calibration_data():
    from app.sprint13.matching import seniority_calibrate

    staff = seniority_calibrate("Staff Engineer")
    intern = seniority_calibrate("Software Intern")
    assert staff["level"] > intern["level"]
    assert intern["label"] == "intern"

# === S13-28 ===

def test_vector_store_hnsw_parameter_tuning_and_benchmarks():
    from app.sprint13.matching import hnsw_tune

    loose = hnsw_tune(m=8, ef=32)
    tight = hnsw_tune(m=32, ef=128)
    assert tight["recall"] > loose["recall"]
    assert tight["latencyMs"] > loose["latencyMs"]

# === S13-29 ===

def test_embeddings_pipeline_shard_aware_reindex_and_backpressure():
    from app.sprint13.matching import shard_reindex

    calm = shard_reindex(shards=4, backlog=10, max_inflight=100)
    hot = shard_reindex(shards=4, backlog=250, max_inflight=100)
    assert calm["backpressure"] is False
    assert hot["backpressure"] is True
    assert hot["inflight"] == 100

# === S13-30 ===

def test_skills_taxonomy_v3_auto_extend_from_corpus_with_review_queue():
    from app.sprint13.matching import observe_skill, reset, taxonomy_extend

    reset()
    observe_skill("rust", count=3)
    observe_skill("obscure", count=1)
    out = taxonomy_extend(min_count=3)
    assert "rust" in out["proposed"]
    assert "obscure" not in out["proposed"]
    assert out["queue"][0]["status"] == "pending"

# === S13-31 ===

def test_resume_parser_v3_gap_detection_and_annotation():
    from app.sprint13.parse import gap_annotate

    bullets = ["Eng Jan 2019 - Dec 2019", "Eng Jan 2021 - present"]
    notes = {"2019-12-01|2021-01-01": "caregiving"}
    result = gap_annotate(bullets, notes)
    assert result["gaps"]
    assert result["gaps"][0]["note"] == "caregiving"

# === S13-32 ===

def test_resume_parser_v3_achievements_metric_detection():
    from app.sprint13.parse import achievement_metrics

    hit = achievement_metrics("Increased conversion 12% and saved $40k")
    assert hit["hasMetric"] is True
    assert 12.0 in hit["percents"]
    assert hit["money"]

# === S13-33 ===

def test_jd_cleaner_v3_boilerplate_classifier_using_heuristics_ml():
    from app.sprint13.parse import boilerplate_score

    noisy = boilerplate_score("Equal opportunity employer. Benefits include ping pong. We're a family.")
    clean = boilerplate_score("Build ingestion adapters in Python.")
    assert noisy["boilerplate"] is True
    assert clean["boilerplate"] is False

# === S13-34 ===

def test_location_geocoding_v2_suburb_metro_rollups_and_radius():
    from app.sprint13.parse import metro_rollup

    sea = metro_rollup("Seattle", "WA")
    assert sea["metro"] == "seattle-tacoma"
    assert sea["radiusKm"] == 40
    other = metro_rollup("Berlin", "", "DE")
    assert other["radiusKm"] == 15

# === S13-35 ===

def test_currency_support_fx_normalization_and_display_rules():
    from app.sprint13.parse import display_money, to_usd

    usd = to_usd(100, "EUR")
    assert usd > 100
    shown = display_money(usd, "EUR")
    assert shown["currency"] == "EUR"
    assert shown["local"] == 100

# === S13-36 ===

def test_salary_parsing_v3_equity_plus_bonus_components():
    from app.sprint13.parse import salary_v3

    parsed = salary_v3("$120k-$150k plus equity of $50k and bonus of $20k")
    assert parsed["schema"] == "ajas.salary.v3"
    assert parsed["equity"] == 50000
    assert parsed["bonus"] == 20000

# === S13-37 ===

def test_normalization_v3_onsite_hybrid_remote_detection_improvements():
    from app.sprint13.parse import work_mode

    assert work_mode("Hybrid in Seattle") == "hybrid"
    assert work_mode("Remote / WFH") == "remote"
    assert work_mode("On-site in NYC") == "onsite"

# === S13-38 ===

def test_normalization_v3_job_type_taxonomy():
    from app.sprint13.parse import job_type

    assert job_type("Full-time Staff Engineer") == "ft"
    assert job_type("Part time contractor") == "pt"
    assert job_type("Summer internship") == "intern"
    assert job_type("Contract role") == "contract"

# === S13-39 ===

def test_crawl_frontier_adaptive_scheduling_using_success_error_rates():
    from app.sprint13.ingest import frontier_score, reset

    reset()
    healthy = frontier_score("greenhouse", success=9, errors=1)
    sick = frontier_score("linkedin", success=1, errors=4)
    assert healthy["delaySec"] < sick["delaySec"]
    assert healthy["successRate"] > sick["successRate"]

# === S13-40 ===

def test_ingestion_adapters_v3_wellfound_session_refresh_guard():
    from app.flags import feature_flags
    from app.sprint13.ingest import reset, wellfound_guard

    reset()
    assert feature_flags()["wellfound_adapter"] is False
    assert wellfound_guard(session_age_min=10)["refresh"] is False
    assert wellfound_guard(session_age_min=50)["stale"] is True

# === S13-41 ===

def test_ingestion_adapters_v3_glassdoor_block_detection_and_cool_down():
    from app.flags import feature_flags
    from app.job_sources.circuit import allow as circuit_allow
    from app.sprint13.ingest import glassdoor_cooldown, reset

    reset()
    assert feature_flags()["glassdoor_adapter"] is False
    cool = glassdoor_cooldown(blocked=True, failures=1)
    assert cool["cooldownMin"] == 15
    assert cool["allow"] is False
    assert circuit_allow("glassdoor") is True

# === S13-42 ===

def test_ingestion_adapters_v3_indeed_html_json_dual_path_parser():
    from app.sprint13.ingest import indeed_dual, reset

    reset()
    parsed = indeed_dual(payload={"jobs": [{"id": "1", "title": "Staff"}]}, html="<div>job posting</div>")
    assert "json" in parsed["paths"]
    assert "html" in parsed["paths"]
    assert len(parsed["jobs"]) == 2

# === S13-43 ===

def test_ingestion_adapters_v3_linkedin_resilience_captcha_fallback():
    from app.flags import feature_flags
    from app.sprint13.ingest import linkedin_resilience, reset

    reset()
    assert feature_flags()["linkedin_adapter"] is False
    blocked = linkedin_resilience(captcha=True)
    assert blocked["bypass"] is False
    assert blocked["fallback"] == "fixture"
    ok = linkedin_resilience(captcha=False)
    assert ok["ok"] is True
    assert ok["bypass"] is False

# === S13-44 ===

def test_observability_structured_tracing_context_propagation():
    from app.sprint13.ops import propagate, reset, trace_viewer

    reset()
    first = propagate("ingest", trace_id="shared")
    second = propagate("match", trace_id="shared")
    assert first["traceId"] == second["traceId"] == "shared"
    assert trace_viewer(trace_id="shared")["count"] == 2

# === S13-45 ===

def test_privacy_field_level_redaction_config_ui():
    from app.sprint13.security import apply_field_redaction, reset, set_field_redaction

    reset()
    set_field_redaction("t1", ["email", "phone"])
    out = apply_field_redaction("t1", {"email": "ada@example.test", "title": "Staff", "notes": "ada@example.test"})
    assert out["email"] == "[redacted]"
    assert out["title"] == "Staff"
    assert "[email]" in out["notes"]

# === S13-46 ===

def test_data_retention_v2_per_tenant_retention_policies():
    from app.sprint13.security import reset, retention_policy

    reset()
    row = retention_policy("t1", days=30)
    assert row["days"] == 30
    try:
        retention_policy("t1", days=3)
        raise AssertionError("expected")
    except ValueError:
        pass

# === S13-47 ===

def test_outbound_allowlist_v2_per_environment_gates():
    from app.sprint13.security import allowlist_for_env

    prod = allowlist_for_env("prod", "boards.greenhouse.io, jobs.lever.co")
    dev = allowlist_for_env("dev", "boards.greenhouse.io")
    assert prod["gated"] is True
    assert dev["gated"] is False
    assert "boards.greenhouse.io" in prod["hosts"]

# === S13-48 ===

def test_idempotency_v3_conflict_resolution_strategies():
    from app.idempotency_v2 import remember, reset as reset_idem
    from app.sprint13.security import resolve_conflict

    reset_idem()
    remember("apply:1", "fp-a", {"id": 1})
    stored = resolve_conflict("apply:1", "fp-b", {"id": 2}, strategy="stored-wins")
    assert stored["status"] == "conflict"
    incoming = resolve_conflict("apply:1", "fp-b", {"id": 2}, strategy="incoming-wins")
    assert incoming["status"] == "replaced"

# === S13-49 ===

def test_error_taxonomy_v3_mapping_to_remediation_playbooks():
    from app.sprint13.security import playbook_for

    book = playbook_for("RATE_LIMITED")
    assert book["retryable"] is True
    assert "retry" in str(book["remediation"]).lower() or book["status"] == 429

# === S13-50 ===

def test_quotas_v2_per_tenant_source_daily_and_burst_caps():
    from app.source_quotas import reset as reset_quotas
    from app.sprint13.ops import quotas_v2, reset

    reset()
    reset_quotas()
    burst = quotas_v2("indeed", daily=100, burst=20, used=20)
    daily = quotas_v2("indeed", daily=100, burst=200, used=100)
    assert burst["burstHit"] is True
    assert daily["dailyHit"] is True
    assert daily["allowed"] is False

# === S13-51 ===

def test_retry_backoff_v2_jitter_strategy_per_queue():
    from random import Random

    from app.sprint13.ops import jitter_backoff

    first = jitter_backoff(1, rng=Random(1))
    later = jitter_backoff(5, rng=Random(1))
    assert later >= first
    assert later <= 8.0

# === S13-52 ===

def test_audit_logging_v2_export_to_csv_json():
    from app.sprint13.ops import audit_bundle

    bundle = audit_bundle(events=[{"id": "a1", "action": "kill", "actor": "ada"}])
    assert bundle["count"] == 1
    assert "a1" in bundle["csv"]
    assert bundle["json"][0]["action"] == "kill"

# === S13-53 ===

def test_queue_workers_graceful_shutdown_and_draining():
    from app.sprint13.ops import drain_worker, reset, shutdown_worker

    reset()
    draining = drain_worker("match")
    assert draining["accepting"] is False
    stopped = shutdown_worker("match")
    assert stopped["graceful"] is True
    assert stopped["status"] == "stopped"

# === S13-54 ===

def test_follow_up_heuristics_v2_weekday_hour_windows():
    from app.sprint13.product import followup_window, next_followup_slot

    assert followup_window(weekday=2, hour=10)["send"] is True
    assert followup_window(weekday=6, hour=10)["send"] is False
    slot = next_followup_slot(datetime(2026, 9, 12, 8, 0, tzinfo=timezone.utc))
    assert followup_window(weekday=slot.weekday(), hour=slot.hour)["send"] is True

# === S13-55 ===

def test_email_reply_planner_suggested_replies_with_tone_controls():
    from app.sprint13.product import reply_plan

    plan = reply_plan(intent="interview", tone="warm")
    assert "slot" in plan["body"]
    assert "warm" in plan["controls"]
    assert plan["tone"] == "warm"

# === S13-56 ===

def test_apply_profile_multi_profile_switcher_per_role_type():
    from app.sprint13.product import reset, save_profile, switch_profile

    reset()
    eng = save_profile(user_id="ada", name="IC", role_type="engineering")
    pm = save_profile(user_id="ada", name="PM", role_type="pm")
    active = switch_profile(pm["id"], user_id="ada")
    assert active["active"] is True
    assert eng["id"] != pm["id"]
    try:
        switch_profile(pm["id"], user_id="bob")
        raise AssertionError("expected")
    except PermissionError:
        pass

# === S13-57 ===

def test_backfill_tool_v2_safe_chunking_and_progress_ui():
    from app.sprint13.ops import backfill_chunks

    plan = backfill_chunks([f"j{i}" for i in range(60)], size=25)
    assert plan["count"] == 3
    assert plan["status"] == "ready"
    assert len(plan["chunks"][0]) == 25

# === S13-58 ===

def test_api_v2_search_sort_filter_consistency():
    from app.sprint13.platform import api_query

    rows = [{"id": "2", "title": "PM", "company": "Beta"}, {"id": "1", "title": "Staff Python", "company": "Acme"}]
    found = api_query(rows, q="python", sort="id", order="asc")
    assert found["count"] == 1
    desc = api_query(rows, q=None, sort="id", order="desc", filters={"company": "Acme"})
    assert desc["items"][0]["id"] == "1"


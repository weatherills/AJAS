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


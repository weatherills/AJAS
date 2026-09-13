"""Sprint 11 task tests. Grows one commit at a time."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings

FIXTURES = Path(__file__).parent / "fixtures"


def _enable_zip(monkeypatch) -> None:
    monkeypatch.setenv("FLAG_ZIPRECRUITER_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)


def test_ziprecruiter_cursor_pages_and_retry_after(monkeypatch):
    from app.job_sources.ziprecruiter import paginate, retry_after_seconds, ziprecruiter_jobs

    payload = json.loads((FIXTURES / "job_boards" / "ziprecruiter_pages.json").read_text())
    pages = paginate(payload)
    assert [job["id"] for job in pages] == ["zr-p1", "zr-p2"]
    assert retry_after_seconds(payload, 0) == 1.5
    _enable_zip(monkeypatch)
    rows = ziprecruiter_jobs(payload, listing_url="https://fixtures.ajas.local/ziprecruiter")
    assert [row["source_posting_id"] for row in rows] == ["zr-p1", "zr-p2"]
    monkeypatch.setenv("FLAG_ZIPRECRUITER_ADAPTER", "false")
    get_settings.cache_clear()
    assert ziprecruiter_jobs(payload) == []


def test_hired_adapter_auth_and_captcha_fallback(monkeypatch):
    from app.job_sources.hired import auth_gate, clear_token, hired_jobs, remember_token

    payload = json.loads((FIXTURES / "job_boards" / "hired.json").read_text())
    clear_token()
    monkeypatch.setenv("FLAG_HIRED_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    monkeypatch.delenv("HIRED_API_TOKEN", raising=False)
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    blocked = auth_gate("<div class='g-recaptcha'></div>")
    assert blocked.captcha is True
    assert blocked.action == "needs_manual"
    assert blocked.bypass is False
    assert hired_jobs(payload, html="<div class='hcaptcha'></div>") == []
    assert hired_jobs(payload) == []
    remember_token("hired-dev-token")
    rows = hired_jobs(payload, listing_url="https://fixtures.ajas.local/hired")
    assert rows and rows[0]["source_posting_id"] == "hi-1"
    clear_token()
    monkeypatch.setenv("FLAG_HIRED_ADAPTER", "false")
    get_settings.cache_clear()
    remember_token("hired-dev-token")
    assert hired_jobs(payload) == []
    clear_token()


def test_greenhouse_career_page_fixture_parser(monkeypatch):
    from app.job_sources.career_pages import greenhouse_career_jobs, parse_career_html

    html = (FIXTURES / "job_boards" / "greenhouse_career.html").read_text()
    cards = parse_career_html(html)
    assert [card["id"] for card in cards] == ["gh-c-1", "gh-c-2"]
    monkeypatch.setenv("FLAG_GREENHOUSE_CAREER_ADAPTER", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = greenhouse_career_jobs(html, listing_url="https://fixtures.ajas.local/greenhouse")
    assert rows[0]["title"] == "Staff Platform Engineer"
    monkeypatch.setenv("FLAG_GREENHOUSE_CAREER_ADAPTER", "false")
    get_settings.cache_clear()
    assert greenhouse_career_jobs(html) == []


def test_lever_career_page_fixture_parser(monkeypatch):
    from app.job_sources.career_pages import lever_career_jobs

    html = (FIXTURES / "job_boards" / "lever_career.html").read_text()
    monkeypatch.setenv("FLAG_LEVER_CAREER_ADAPTER", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = lever_career_jobs(html, listing_url="https://fixtures.ajas.local/lever")
    assert rows[0]["source_posting_id"] == "lv-c-1"
    assert rows[0]["company"] == "Fabrikam"
    monkeypatch.setenv("FLAG_LEVER_CAREER_ADAPTER", "false")
    get_settings.cache_clear()
    assert lever_career_jobs(html) == []


def test_workday_career_page_fixture_parser(monkeypatch):
    from app.job_sources.career_pages import workday_career_jobs

    html = (FIXTURES / "job_boards" / "workday_career.html").read_text()
    monkeypatch.setenv("FLAG_WORKDAY_ADAPTER", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = workday_career_jobs(html, listing_url="https://fixtures.ajas.local/workday")
    assert rows[0]["source_posting_id"] == "wd-c-1"
    assert "Workday" in rows[0]["title"]
    monkeypatch.setenv("FLAG_WORKDAY_ADAPTER", "false")
    get_settings.cache_clear()
    assert workday_career_jobs(html) == []


def test_source_adapter_watchdog_retries_on_dom_drift():
    from app.job_sources.drift import reset
    from app.job_sources.watchdog import retry_on_drift

    reset()
    payloads = [
        {"jobs": [{"id": "1"}], "etag": "a"},
        {"jobs": [{"id": "1"}], "ts": "later"},
        {"jobs": [{"id": "2", "title": "New"}]},
    ]
    calls: list[int] = []

    def loader(payload):
        calls.append(1)
        jobs = payload.get("jobs") if isinstance(payload, dict) else []
        return jobs

    first = retry_on_drift("canary-src", payloads[0], loader)
    assert first["attempts"] == 1
    assert first["recovered"] is True
    same_shape = retry_on_drift("canary-src", payloads[1], loader)
    assert same_shape["changed"] is False
    drifted = retry_on_drift("canary-src", payloads[2], loader)
    assert drifted["changed"] is True
    assert drifted["jobs"] == [{"id": "2", "title": "New"}]
    assert len(calls) >= 3


def test_source_adapter_canary_html_snapshot_drift(tmp_path):
    from app.job_sources.canary import check_snapshot, run_canaries

    html = tmp_path / "board.html"
    html.write_text("<div>v1</div>")
    (tmp_path / "board.html.sha256").write_text("deadbeef\n")
    bad = check_snapshot("board.html", tmp_path)
    assert bad["ok"] is False
    (tmp_path / "board.html.sha256").write_text(bad["digest"] + "\n")
    good = check_snapshot("board.html", tmp_path)
    assert good["ok"] is True
    batch = run_canaries(["greenhouse_career.html", "lever_career.html", "workday_career.html"])
    assert batch["ok"] is True
    assert batch["checked"] == 3


def test_benefits_perks_schema_extraction():
    from app.job_sources.benefits import CANONICAL, extract_benefits

    parsed = extract_benefits(
        "Medical insurance, dental, vision, 401k match, RSUs, unlimited PTO, parental leave, WFH stipend, learning budget."
    )
    assert parsed["schema"] == "ajas.benefits.v1"
    assert parsed["canonical"] == list(CANONICAL)
    for key in ("health_insurance", "dental", "vision", "401k", "equity", "pto", "parental_leave", "remote_stipend", "learning_budget"):
        assert key in parsed["benefits"]


def test_onsite_percent_and_travel_requirement_fields():
    from app.job_sources.work_arrangement import work_arrangement

    hybrid = work_arrangement("3 days a week in-office, occasional travel, 80% remote ok")
    assert hybrid["onsite_percent"] == 60
    assert hybrid["travel_percent"] == 10
    travel = work_arrangement("Travel up to 25%, no remote")
    assert travel["travel_percent"] == 25
    none = work_arrangement("Fully remote, no travel")
    assert none["travel_percent"] == 0


def test_location_timezone_inference_and_normalization():
    from app.job_sources.timezone import infer_timezone

    assert infer_timezone("Seattle, WA")["timezone"] == "America/Los_Angeles"
    assert infer_timezone("Austin, TX")["timezone"] == "America/Chicago"
    assert infer_timezone("Dublin")["timezone"] == "Europe/Dublin"
    assert infer_timezone("Remote")["timezone"] == "UTC"
    assert infer_timezone("Unknownville")["timezone"] is None


def test_salary_equity_bonus_extraction():
    from app.job_sources.comp import parse_comp

    parsed = parse_comp("$140,000-$165,000 plus 0.15% equity and 10% bonus, signing bonus $10k")
    assert parsed["min"] == 140000
    assert parsed["equityPercent"] == 0.15
    assert parsed["bonusPercent"] == 10
    assert parsed["signingBonus"] == 10000

def test_embeddings_batch_size_autotune_from_latency():
    from app.matching.batch_autotune import BatchAutotune

    tuner = BatchAutotune(size=16, target_ms=200, min_size=4, max_size=64)
    assert tuner.record(400) == 8
    assert tuner.record(50, batch_size=8) == 16

def test_embeddings_cold_start_cache_priming():
    from app.matching.embed_cache import EmbeddingCache

    cache = EmbeddingCache(max_items=8)
    primed = cache.prime(["python azure", "react typescript"])
    assert primed == 2
    cache.get("python azure")
    assert cache.hits >= 1
    assert cache.misses == 2

def test_ann_recall_evaluation_harness():
    from app.matching.ann import evaluate_recall, search
    from app.matching.vectors import VectorStore

    store = VectorStore()
    store.upsert("a", [1.0, 0.0, 0.0])
    store.upsert("b", [0.9, 0.1, 0.0])
    store.upsert("c", [0.0, 1.0, 0.0])
    ranked = search(store, [1.0, 0.0, 0.0], k=2)
    assert ranked[0][0] == "a"
    metrics = evaluate_recall(store, [{"vector": [1.0, 0.0, 0.0], "relevant": ["a", "b"]}], k=2)
    assert metrics["recall"] == 1.0

def test_skills_gap_penalty_curve_calibration():
    from app.matching.gap_penalty import apply_gap_penalty, gap_penalty

    assert gap_penalty(0) == 0.0
    assert 0 < gap_penalty(1) < gap_penalty(4) <= 35.0
    job = "Required:\n- kubernetes\n- rust\n"
    adjusted = apply_gap_penalty(80.0, "python azure", job)
    assert adjusted["missing"] >= 1
    assert adjusted["score"] < 80.0

def test_preferred_tech_stack_boost_from_prds():
    from app.matching.stack_boost import PRD_STACK, stack_boost

    result = stack_boost("python typescript react azure", "python azure react services")
    assert "python" in result["hits"]
    assert result["boost"] > 0
    assert "python" in PRD_STACK

def test_employment_type_alignment_ft_pt_contract():
    from app.matching.employment import alignment, normalize_employment_type

    assert normalize_employment_type("Full-time") == "full_time"
    assert normalize_employment_type("C2C contract") == "contract"
    hit = alignment("full time", "FT")
    miss = alignment("full time", "part-time")
    assert hit["aligned"] is True and hit["delta"] == 0.0
    assert miss["aligned"] is False and miss["delta"] < 0

def test_ranking_cross_feature_normalization_fairness():
    from app.matching.fair_norm import normalize_features

    rows = [
        {"id": "g", "score": 90, "keyword": 80, "semantic": 70, "source": "greenhouse"},
        {"id": "l", "score": 45, "keyword": 40, "semantic": 35, "source": "lever"},
    ]
    out = normalize_features(rows)
    assert out[0]["score_norm"] == 1.0
    assert out[1]["score_norm"] == 0.0
    assert "fair_score" in out[0]

def test_ranking_tie_breakers_for_identical_scores():
    from app.matching.ties import sort_with_ties

    rows = [
        {"id": "b", "score": 80, "posted_at": "2026-01-01", "source_type": "lever"},
        {"id": "a", "score": 80, "posted_at": "2026-06-01", "source_type": "greenhouse"},
        {"id": "c", "score": 90, "posted_at": "2026-01-01", "source_type": "greenhouse"},
    ]
    ordered = sort_with_ties(rows)
    assert [row["id"] for row in ordered] == ["c", "a", "b"]


def test_explanations_counterfactual_resume_suggestions():
    from app.matching.counterfactual import counterfactuals

    result = counterfactuals("python azure", "Required:\n- kubernetes\n- rust\n")
    assert result["add"]
    assert any("kubernetes" in item or "rust" in item for item in result["suggestions"])
    assert result["lift_if_all_added"] > 0

def test_explanations_skill_mismatch_counts():
    from app.matching.mismatch_counts import mismatch_counts
    result = mismatch_counts("python azure", "python python rust")
    terms = [row["term"] for row in result["missing"]]
    assert "rust" in terms

def test_resume_achievements_vs_responsibilities_classifier():
    from app.resumes.achievements import classify_resume
    result = classify_resume(["Increased conversion 12%", "Responsible for on-call"])
    assert result["achievements"] == 1
    assert result["responsibilities"] == 1

def test_resume_gap_detection_and_annotation():
    from app.resumes.gap_notes import annotate_gaps
    bullets = ["Eng Jan 2019 - Dec 2019", "Eng Jan 2021 - present"]
    notes = {"2019-12-01|2021-01-01": "caregiving"}
    result = annotate_gaps(bullets, notes=notes)
    assert result["gaps"]
    assert result["gaps"][0]["note"] == "caregiving"

def test_resume_multilingual_detection_and_routing():
    from app.resumes.lang_router import route
    es = route("Experiencia laboral y habilidades en python")
    assert es["lang"] == "es" and es["route"] == "es_es"
    en = route("Experience and skills in python")
    assert en["lang"] == "en"

def test_skills_taxonomy_community_synonyms_import():
    from app.matching.synonyms_import import import_rows
    from app.matching.taxonomy import canonical_skill
    stats = import_rows([{"canonical": "python", "alias": "cpy"}])
    assert stats["added"] >= 1
    assert canonical_skill("cpy") == "python"

def test_skills_taxonomy_deprecate_outdated_terms():
    from app.matching.taxonomy_alias import apply_deprecations, resolve
    apply_deprecations()
    hit = resolve("angularjs")
    assert hit["deprecated"] is True
    assert hit["canonical"] == "javascript"

def test_apply_form_state_machine_core():
    from app.auto_apply.form_machine import next_state
    assert next_state("draft", "start") == "profile"
    assert next_state("review", "submit") == "submit"
    assert next_state("submit", "ok") == "done"
    assert next_state("questions", "next", payload="<div class='g-recaptcha'>") == "needs_manual"

def test_apply_upload_fallback_retrier():
    from app.auto_apply.upload_retry import upload_with_retry
    calls = {"n": 0}
    def send():
        calls["n"] += 1
        return {"ok": calls["n"] >= 2}
    out = upload_with_retry(send, attempts=3)
    assert out["ok"] is True and out["attempts"] == 2
    blocked = upload_with_retry(lambda: {"ok": False, "captcha": True}, attempts=3)
    assert blocked["action"] == "needs_manual"

def test_cover_letter_role_specific_templates():
    from app.auto_apply.cover_roles import render_role_cover
    letter = render_role_cover(role_family="frontend", role="FE", company="Acme", name="Ava")
    assert letter["roleFamily"] == "frontend"
    assert "accessible" in letter["text"].lower() or "UI" in letter["text"]

def test_cover_letter_parameterize_resume_highlights():
    from app.auto_apply.highlights import select_highlights
    picks = select_highlights(
        ["Increased API p99 by 40% with python", "Responsible for snacks"],
        "python API reliability",
        limit=1,
    )
    assert picks and "python" in picks[0]["text"].lower()


def test_email_oauth2_token_refresh_and_errors():
    from app.mail.oauth_hardening import refresh_access_token

    ok = refresh_access_token(refresh_token="r1", access_token="a1")
    assert ok["ok"] is True and ok["accessToken"] == "a1"
    dead = refresh_access_token(refresh_token="r1", status=401, body="invalid_grant")
    assert dead["ok"] is False and dead["action"] == "reconnect"
    scope = refresh_access_token(refresh_token="r1", status=403, body="insufficient_scope")
    assert scope["action"] == "reconsent"
    busy = refresh_access_token(refresh_token="r1", status=429)
    assert busy["retry"] is True and busy["action"] == "retry"
    missing = refresh_access_token(refresh_token="")
    assert missing["action"] == "reconnect"


def test_email_interview_time_tz_normalization():
    from app.mail.interview_time import parse_interview_time

    hit = parse_interview_time("Interview on March 3, 2026 at 2:00 pm", location="New York")
    assert hit["ok"] is True
    assert hit["timezone"] == "America/New_York"
    assert hit["utc"] == "2026-03-03T19:00:00Z"
    iso = parse_interview_time("Meet 2026-09-13 09:30", timezone_name="UTC")
    assert iso["utc"] == "2026-09-13T09:30:00Z"


def test_email_signature_quoted_text_stripping():
    from app.mail.strip_quotes import strip_quoted

    body = "Please reply Tuesday.\n\n--\nAva Recruiter\n> old quote\nOn Mon Jane wrote:\nprior"
    assert strip_quoted(body) == "Please reply Tuesday."
    quoted = "Can you join?\n> On Mon, Jane wrote:\n> prior thread"
    assert strip_quoted(quoted) == "Can you join?"


def test_followup_snooze_until_business_hours():
    from datetime import datetime, timezone

    from app.mail.snooze import snooze_until

    saturday = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    out = snooze_until(now=saturday, until=saturday, business_hours=True)
    assert out["until"].startswith("2026-09-14T09:00:00")
    assert out["rolled"] is True
    weekday = datetime(2026, 9, 14, 10, 30, tzinfo=timezone.utc)
    same = snooze_until(now=weekday, until=weekday, business_hours=True)
    assert same["until"].startswith("2026-09-14T10:30:00")
    assert same["rolled"] is False


def test_distributed_trace_propagation_across_workers():
    from app.request_context import current_request_id, set_request_id
    from app.tracing import bind_worker, propagate, start_span

    set_request_id("trace-s11")
    headers = propagate()
    assert headers["X-Request-Id"] == "trace-s11"
    bound = bind_worker(headers)
    assert bound == "trace-s11"
    assert current_request_id() == "trace-s11"
    span = start_span("worker.ingest")
    assert span["traceId"] == "trace-s11"


def test_structured_error_contexts_with_request_ids():
    from app.observability import error_context
    from app.request_context import set_request_id

    set_request_id("req-42")
    ctx = error_context(code="APPLY_FAILED", message="user ada@example.com failed", jobId="job-1")
    assert ctx["requestId"] == "req-42"
    assert ctx["code"] == "APPLY_FAILED"
    assert "[redacted-email]" in ctx["message"]
    assert ctx["jobId"] == "job-1"


def test_per_source_success_latency_histograms():
    from app.source_metrics import histogram, observe, reset

    reset()
    observe("greenhouse", ok=True, latency_ms=40)
    observe("greenhouse", ok=False, latency_ms=900)
    body = histogram("greenhouse")
    assert body["count"] == 2
    assert body["ok"] == 1
    assert body["buckets"]["le_50"] == 1
    assert body["buckets"]["le_1000"] == 1


def test_noisy_adapter_mute_unmute():
    from app.adapter_mute import is_muted, listing, mute, reset, unmute
    from app.ingestion_alerts import maybe_alert

    reset()
    mute("workday")
    assert is_muted("workday")
    assert listing() == ["workday"]
    assert maybe_alert(failure_count=9, source="workday") is False
    unmute("workday")
    assert is_muted("workday") is False


def test_pii_scrubbing_rules_v2():
    from app.privacy_review import scrub_v2

    out = scrub_v2({"email": "ada@example.com", "note": "call +1 (555) 555-0100", "nested": {"token": "secret"}})
    assert out["email"] == "[redacted]"
    assert "[redacted-phone]" in out["note"]
    assert out["nested"]["token"] == "[redacted]"


def test_consent_log_for_automated_applies():
    from app.auto_apply.consent_log import listing, record, reset

    reset()
    row = record(user_id="ada", job_id="job-1", resume_id="r1", approved=True)
    assert row["approved"] is True and row["bulk"] is False
    assert listing(user_id="ada")[0]["jobId"] == "job-1"


def test_user_data_export_bundle_includes_resumes_and_logs():
    from app.privacy import export_bundle

    bundle = export_bundle(user_id="ada", resumes=[{"id": "r1"}], logs=[{"id": "l1"}])
    assert bundle["resumes"][0]["id"] == "r1"
    assert bundle["logs"][0]["id"] == "l1"
    assert bundle["format"] == "ajas.gdpr.v1"


def test_retention_policies_per_artifact_type():
    from app.retention import expired, policy, retention_days

    assert retention_days("logs") == 30
    assert policy()["schema"] == "ajas.retention.v1"
    assert expired("logs", "2020-01-01T00:00:00Z") is True


def test_outbound_allowlist_editor_audit():
    from app.allowlist import audit_log, reset_audit, set_policy

    reset_audit()
    body = set_policy("Boards.greenhouse.io, jobs.lever.co", actor="ada")
    assert "boards.greenhouse.io" in body["hosts"]
    assert audit_log()[0]["actor"] == "ada"


def test_permission_model_hardening_multi_tenant():
    from app.auth import Principal
    from app.rbac import permissions_payload, tenant_allowed

    user = Principal(user_id="ada", scopes=frozenset())
    admin = Principal(user_id="local-admin", scopes=frozenset({"admin"}))
    assert permissions_payload(user)["permissions"]["tenantAdmin"] is False
    assert tenant_allowed(user, "ada") is True
    assert tenant_allowed(user, "other") is False
    assert tenant_allowed(admin, "other") is True


def test_secrets_rotation_job_with_drift_detection():
    from app.secrets_rotate import reset, rotate

    reset()
    first = rotate("graph", "old-secret")
    drifted = rotate("graph", "new-secret", previous="wrong")
    assert first["rotated"] is True
    assert drifted["drift"] is True


def test_adaptive_backpressure_by_queue_depth():
    from app.queue_backpressure import backpressure

    assert backpressure(10)["mode"] == "open"
    assert backpressure(120)["mode"] == "slow"
    assert backpressure(500)["admit"] is False


def test_dlq_replayer_with_sampling_guard():
    from app.dlq import enqueue, replay, reset

    reset()
    item = enqueue({"id": "dlq-9", "token": "secret"})
    skipped = replay(item["id"], sample_rate=0.1, roll=0.9)
    assert skipped["status"] == "sampled_skip"
    replayed = replay(item["id"], sample_rate=1.0)
    assert replayed["status"] == "queued"


def test_idempotent_task_envelopes_v2():
    from app.idempotency_v2 import envelope

    one = envelope("ingest", {"source": "greenhouse"})
    two = envelope("ingest", {"source": "greenhouse"})
    assert one["schema"] == "ajas.envelope.v2"
    assert one["fingerprint"] == two["fingerprint"]


def test_health_dependency_matrix_live_probes():
    from app.features.health import _status_payload

    body = _status_payload()
    assert body["probes"]["workers"]["ok"] is True
    assert "openai" in body["dependencyMatrix"]


def test_db_connection_pool_autotune():
    from app.db_pool import autotune

    grow = autotune(latency_ms=400, current=4)
    assert grow["action"] == "grow" and grow["size"] == 6
    shrink = autotune(latency_ms=10, current=4)
    assert shrink["action"] == "shrink"


def test_caching_layer_for_hot_list_detail_queries():
    from app.query_cache import get_or_set, reset

    reset()
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return {"items": [1]}

    assert get_or_set("jobs:list", factory)["items"] == [1]
    assert get_or_set("jobs:list", factory)["items"] == [1]
    assert calls["n"] == 1


def test_batch_writer_for_logs_and_matches():
    from app.batch_writes import write_logs_and_matches

    seen: list[list] = []
    out = write_logs_and_matches(logs=[{"id": "l1"}], matches=[{"id": "m1"}], size=10, writer=seen.append)
    assert out["logs"] == 1 and out["matches"] == 1
    assert out["written"] == 2


def test_indices_for_common_filters_sorts():
    from app.db_indices import FILTER_SORT_INDICES, index_policy

    paths = [item["path"] for item in index_policy()["includedPaths"]]
    assert "/location" in paths and "/score" in FILTER_SORT_INDICES


def test_job_revisions_table_for_jd_diffing():
    from app.job_sources.revisions import diff_revisions, listing, record, reset

    reset()
    record("job-1", "Python services")
    record("job-1", "Python services on Azure")
    assert len(listing("job-1")) == 2
    diff = diff_revisions("job-1", 1, 2)
    assert diff["ok"] is True and diff["changed"] is True


def test_api_filter_sort_paginate_matches():
    from app.list_query import page_rows

    rows = [{"score": 10, "id": "a"}, {"score": 90, "id": "b"}]
    page = page_rows(rows, cursor=None, limit=1, sort="score", order="desc")
    assert page["items"][0]["id"] == "b"
    assert page["nextCursor"] == "1"


def test_api_job_revisions_and_diff_endpoints(monkeypatch):
    import azure.functions as func

    from app.config import get_settings
    from app.features import source_ingestion as routes
    from app.job_sources.revisions import reset

    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    reset()

    def req(method, url, *, json_body=None, params=None, route=None):
        hdrs = {"Authorization": "Bearer local-user"}
        body = b""
        if json_body is not None:
            hdrs["Content-Type"] = "application/json"
            body = json.dumps(json_body).encode()
        return func.HttpRequest(method=method, url=url, headers=hdrs, params=params or {}, route_params=route or {}, body=body)

    created = json.loads(
        routes.job_revisions(req("POST", "http://localhost/api/v1/jobs/j1/revisions", json_body={"description": "v1"}, route={"id": "j1"})).get_body()
    )
    assert created["revision"] == 1
    listed = json.loads(routes.job_revisions(req("GET", "http://localhost/api/v1/jobs/j1/revisions", route={"id": "j1"})).get_body())
    assert listed["items"][0]["jobId"] == "j1"


def test_api_email_thread_query_helpers():
    from app.mail.thread_query import query_threads

    page = query_threads(
        [
            {"id": "t1", "subject": "Interview", "snippet": "Tuesday", "jobId": "j1", "linked": True, "lastMessageAt": "2026-09-13"},
            {"id": "t2", "subject": "Offer", "snippet": "congrats", "jobId": None, "linked": False, "lastMessageAt": "2026-09-12"},
        ],
        q="interview",
        limit=10,
    )
    assert page["items"][0]["id"] == "t1"


def test_api_saved_search_crud(monkeypatch):
    import azure.functions as func

    from app.config import get_settings
    from app.features import settings as routes
    from app.saved_searches import reset

    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    reset()

    def req(method, url, *, json_body=None, route=None):
        hdrs = {"Authorization": "Bearer local-user"}
        body = b""
        if json_body is not None:
            hdrs["Content-Type"] = "application/json"
            body = json.dumps(json_body).encode()
        return func.HttpRequest(method=method, url=url, headers=hdrs, params={}, route_params=route or {}, body=body)

    created = json.loads(
        routes.saved_searches(req("POST", "http://localhost/api/v1/saved-searches", json_body={"name": "Remote", "filters": {"q": "staff"}, "alertsEnabled": True})).get_body()
    )
    assert created["alertsEnabled"] is True
    listed = json.loads(routes.saved_searches(req("GET", "http://localhost/api/v1/saved-searches")).get_body())
    assert listed["items"][0]["name"] == "Remote"


def test_api_auth_scoped_tokens_for_ingestion():
    from app.automation_tokens import authorize_ingest, issue

    token = issue("ada", ["ingest"])
    assert authorize_ingest(token.token) is True
    other = issue("ada", ["apply"])
    assert authorize_ingest(other.token) is False


def test_webhooks_signed_events_for_email_and_applies():
    from app.webhooks_sig import signed_event, verify_signature
    import json

    event = signed_event("s3cret", "email.status", {"threadId": "t1"})
    body = json.dumps({"type": event["type"], "payload": event["payload"]}, sort_keys=True, default=str)
    assert verify_signature("s3cret", body, event["signature"]) is True


def test_cli_adapter_verification_dry_run_includes_hired():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "verify_adapters.py"
    spec = importlib.util.spec_from_file_location("verify_adapters_s11", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    assert "hired" in mod.ADAPTERS
    result = mod.dry_run("hired")
    assert result["dryRun"] is True


def test_cli_bulk_renormalize_with_current_rules():
    from app.job_sources.legacy_migrate import migrate_job

    row = migrate_job({"title": "Eng", "location": "Austin, TX", "description": "health insurance and 10% equity"})
    assert row["normalized"] is True
    assert row["timezone"]["timezone"] == "America/Chicago"


def test_backfill_embeddings_reindex_orchestrator():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "reindex_embeddings.py"
    spec = importlib.util.spec_from_file_location("reindex_embeddings_s11", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    body = mod.orchestrate(batch_size=10)
    assert body["orchestrated"] is True
    assert "reindexed" in body


def test_backfill_migrate_legacy_jobs_to_new_normalization():
    from app.job_sources.legacy_migrate import migrate_many

    out = migrate_many([{"title": "Eng", "location": "Remote", "description": "python"}])
    assert out["count"] == 1
    assert out["items"][0]["schema"] == "ajas.job.v2"


def test_html_snapshots_for_new_sources():
    from app.job_sources.canary import check_snapshot

    assert check_snapshot("hired_career.html")["ok"] is True
    assert check_snapshot("indeed_career.html")["ok"] is True


def test_email_templates_invite_reject_reschedule():
    from app.mail.parser_templates import TEMPLATES

    assert "invite" in TEMPLATES and "reject" in TEMPLATES and "reschedule" in TEMPLATES
    invite = (FIXTURES / "email" / "invite.txt").read_text()
    assert "interview" in invite.lower()

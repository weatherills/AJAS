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


def test_followup_sla_24_and_72_hour_reminders():
    from datetime import datetime, timezone, timedelta
    from app.mail.sla import followup_reminders

    now = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
    inbound = now - timedelta(hours=30)
    mid = followup_reminders(last_inbound_at=inbound, now=now)
    assert 24 in mid["due"]
    assert 72 not in mid["due"]
    late = followup_reminders(last_inbound_at=now - timedelta(hours=80), now=now)
    assert late["due"] == [24, 72]
    replied = followup_reminders(last_inbound_at=inbound, last_outbound_at=now - timedelta(hours=1), now=now)
    assert replied["replied"] is True


def test_notification_center_toasts_and_digest():
    from app.notify import digest_email, push, reset

    reset()
    push(kind="match", title="New match", body="Staff Engineer at Acme")
    digest = digest_email()
    assert digest["count"] == 1
    assert "Staff Engineer" in digest["text"]


def test_audit_trail_filter_and_csv_export():
    from app.audit import record_action
    from app.audit_query import export_csv, filter_actions

    record_action(actor="ada", action="ingest", target="job-1")
    record_action(actor="linus", action="apply", target="job-2")
    rows = filter_actions(actor="ada", action="ingest")
    assert rows and rows[-1]["actor"] == "ada"
    csv_text = export_csv(rows)
    assert "actor" in csv_text.splitlines()[0]
    assert "ingest" in csv_text


def test_error_taxonomy_v2_http_and_remediation():
    from app.errors import error_taxonomy

    row = error_taxonomy("INGESTION_FAILED")
    assert row["status"] == 502
    assert row["retryable"] is True
    assert "circuit breaker" in str(row["remediation"]).lower()
    aliased = error_taxonomy("BAD_INPUT")
    assert aliased["canonical"] == "INVALID_INPUT"
    assert aliased["status"] == 400


def test_pipeline_trace_ids_span_ingest_match_apply():
    from app.pipeline_trace import complete_stage, pipeline_trace_id, trace_stage

    trace_id = pipeline_trace_id()
    ingest = trace_stage("ingest", trace_id=trace_id, source="greenhouse")
    match = trace_stage("match", trace_id=trace_id, job_id="job-1")
    apply = trace_stage("apply", trace_id=trace_id, job_id="job-1")
    done = [complete_stage(ingest), complete_stage(match), complete_stage(apply)]
    assert {row["traceId"] for row in done} == {trace_id}
    assert [row["name"] for row in done] == ["pipeline.ingest", "pipeline.match", "pipeline.apply"]


def test_metrics_dashboard_snapshot_series():
    from app.metrics import increment, reset, snapshot

    reset()
    increment("ingest.jobs", 3)
    increment("match.compute", 2)
    body = snapshot()
    names = [row["name"] for row in body["series"]]
    assert "Ingestion" in names
    assert body["counters"]["ingest.jobs"] == 3


def test_adaptive_alert_thresholds_dampen_noise():
    from app.alerts import observe

    baseline = None
    for _ in range(8):
        baseline = observe("ingest.failures", 2)
    spike = observe("ingest.failures", 40)
    assert baseline and baseline["alert"] is False
    assert spike["alert"] is True
    assert spike["threshold"] > baseline["mean"]


def test_gdpr_on_demand_export_bundle():
    from app.privacy import export_bundle

    bundle = export_bundle(user_id="ada", jobs=[{"id": "j1"}], emails=[], matches=[])
    assert bundle["userId"] == "ada"
    assert bundle["format"] == "ajas.gdpr.v1"
    assert bundle["jobs"][0]["id"] == "j1"


def test_right_to_be_forgotten_purge_job():
    from app.privacy import apply_purge, purge_plan

    plan = purge_plan(
        user_id="ada",
        jobs=[{"id": "j1", "user_id": "ada"}],
        emails=[{"id": "e1", "user_id": "ada"}],
        matches=[{"id": "m1", "user_id": "ada"}],
    )
    result = apply_purge(plan)
    assert result["status"] == "purged"
    assert result["deleted"] == 3


def test_outbound_allowlist_policy_parser():
    from app.allowlist import parse_policy, policy_text

    hosts = parse_policy("Boards.greenhouse.io, jobs.lever.co")
    assert hosts == ["boards.greenhouse.io", "jobs.lever.co"]
    assert "greenhouse" in policy_text(hosts)


def test_secrets_hot_reload_adapters():
    from app.secrets_reload import current_version, reload_adapters

    before = current_version()
    result = reload_adapters()
    assert result["version"] == before + 1
    assert current_version() == result["version"]


def test_rate_limit_policy_v2_per_tenant_and_endpoint():
    from app.ratelimit_v2 import hit, reset

    reset()
    first = hit("ada", "/jobs", limit=2, now=1.0)
    second = hit("ada", "/jobs", limit=2, now=1.1)
    third = hit("ada", "/jobs", limit=2, now=1.2)
    other = hit("ada", "/matches", limit=2, now=1.2)
    assert first["allowed"] and second["allowed"]
    assert third["allowed"] is False
    assert other["allowed"] is True
    assert other["count"] == 1


def test_idempotency_keys_v2_window_and_conflicts():
    from app.idempotency_v2 import conflicts, remember, reset

    reset()
    first = remember("k1", "fp-a", {"ok": True}, now=10, ttl_sec=5)
    clash = remember("k1", "fp-b", {"ok": False}, now=11, ttl_sec=5)
    assert first["status"] == "stored"
    assert clash["status"] == "conflict"
    assert conflicts()


def test_queue_health_stuck_job_auto_requeue():
    from app.queue_health import QueueJob, requeue

    jobs = [QueueJob(id="q1", queue="ingest", started_at=0, attempts=0, status="running")]
    result = requeue(jobs, now=400, timeout_sec=300)
    assert result["retried"] == 1
    assert jobs[0].status == "queued"


def test_dead_letter_queue_inspect_retry_redaction():
    from app.dlq import enqueue, inspect, reset, retry

    reset()
    row = enqueue({"id": "dlq-1", "title": "Staff", "token": "super-secret"})
    assert row["payload"]["token"] == "[redacted]"
    assert inspect("dlq-1")["status"] == "dead"
    assert retry("dlq-1")["status"] == "queued"


def test_backfill_renormalizes_historical_jobs():
    from app.job_sources.backfill import backfill_jobs

    result = backfill_jobs(
        [{"title": "Staff Engineer", "company": "Acme", "location": "Remote", "body": "Compensation $120,000-$150,000\npython azure"}]
    )
    assert result["count"] == 1
    assert result["items"][0]["salaryMin"] == 120000


def test_cli_verify_adapters_dry_run(monkeypatch):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "verify_adapters.py"
    spec = importlib.util.spec_from_file_location("verify_adapters", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    monkeypatch.setenv("FLAG_GLASSDOOR_ADAPTER", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    result = mod.dry_run("glassdoor")
    assert result["dryRun"] is True
    assert result["source"] == "glassdoor"
    assert result["count"] == 0


def test_e2e_ingestion_ranking_explain_regression(monkeypatch):
    import json
    from pathlib import Path
    from app.config import get_settings
    from app.job_sources.boards import glassdoor_jobs
    from app.job_sources.enrich import enrich_posting
    from app.matching.fairness import dedupe_roles
    from app.matching.spans import reason_spans

    payload = json.loads((Path(__file__).parent / "fixtures" / "job_boards" / "glassdoor.json").read_text())
    monkeypatch.setenv("FLAG_GLASSDOOR_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = glassdoor_jobs(payload, listing_url="https://fixtures.ajas.local/glassdoor")
    assert rows
    ranked = []
    for row in rows:
        extra = enrich_posting(title=row["title"], company=row["company"], location=row["location"], body=row["body"])
        spans = reason_spans(job_text=extra["description"], highlights=["python"], gaps=[])
        ranked.append({**row, **extra, "score": 70, "spans": spans})
    kept = dedupe_roles(ranked)
    assert kept
    assert kept[0]["salaryMin"]
    assert any(span["token"].lower() == "python" for span in kept[0]["spans"]["matched"])


def test_e2e_email_parser_templates_invite_reject_neutral():
    from app.mail.intent import classify_email
    from app.mail.parser_templates import TEMPLATES

    invite = classify_email(subject=TEMPLATES["invite"]["subject"], body=TEMPLATES["invite"]["body"])
    reject = classify_email(subject=TEMPLATES["reject"]["subject"], body=TEMPLATES["reject"]["body"])
    neutral = classify_email(subject=TEMPLATES["neutral"]["subject"], body=TEMPLATES["neutral"]["body"])
    assert invite["intent"] == "interview"
    assert reject["intent"] == "rejection"
    assert neutral["intent"] in {"generic", "follow_up"}


def test_salary_geo_negation_edge_cases():
    from app.job_sources.geocode import geocode
    from app.job_sources.salary import parse_salary_v2
    from app.matching.skills_v2 import extract_skills_v2

    yenish = parse_salary_v2("CAD 95k to 120k")
    assert yenish["currency"] == "CAD"
    london = geocode("London", "", "UK")
    assert london["found"] is True
    skills = extract_skills_v2("Required: Python.\nNo Java.\nIs not required: COBOL")
    joined = " ".join(skills["skills"])
    denied = " ".join(skills["negated"])
    assert "python" in joined
    assert "java" in denied
    assert "cobol" in denied


def test_html_snapshots_exist_for_new_adapters():
    from pathlib import Path

    fixtures = Path(__file__).parent / "fixtures" / "job_boards"
    glassdoor = (fixtures / "glassdoor.html").read_text()
    wellfound = (fixtures / "wellfound.html").read_text()
    assert "gd-html-1" in glassdoor
    assert "wf-html-1" in wellfound
    assert "not scraped live" in glassdoor.lower() or "fixture" in glassdoor.lower()


def test_seed_data_v2_varied_resumes():
    from app.resumes.seeds_v2 import seed_resumes

    seeds = seed_resumes()
    assert set(seeds) == {"junior", "mid", "senior", "remote-only"}
    assert "intern" in seeds["junior"].lower()
    assert "staff" in seeds["senior"].lower()
    assert "remote" in seeds["remote-only"].lower()


def test_api_pagination_and_sorting_jobs_matches():
    from app.list_query import page_rows

    rows = [
        {"id": "a", "updatedAt": "2026-01-01", "score": 40},
        {"id": "b", "updatedAt": "2026-09-01", "score": 90},
        {"id": "c", "updatedAt": "2026-06-01", "score": 70},
    ]
    page = page_rows(rows, cursor=None, limit=2, sort="score", order="desc")
    assert [item["id"] for item in page["items"]] == ["b", "c"]
    assert page["nextCursor"] == "2"
    assert page["total"] == 3


def test_scoped_automation_tokens():
    from app.automation_tokens import authorize, issue

    token = issue("ada", ["ingest", "apply", "nope"])
    assert authorize(token.token, "ingest") is True
    assert authorize(token.token, "match") is False
    assert "nope" not in token.scopes


def test_webhook_signature_verification():
    from app.webhooks_sig import sign_payload, verify_signature

    body = '{"event":"ingest.completed","jobId":"gd-1"}'
    header = sign_payload("s3cret", body)
    assert header.startswith("sha256=")
    assert verify_signature("s3cret", body, header) is True
    assert verify_signature("s3cret", body, "sha256=deadbeef") is False


def test_health_endpoints_v2_dependency_matrix_and_version():
    from app.features.health import _status_payload

    body = _status_payload()
    assert body["version"] == "sprint13"
    assert body["dependencyMatrix"]["workers"]["match"] is True
    assert "cosmos" in body["dependencyMatrix"]


def test_hot_query_cache_ttl():
    from app.query_cache import get_item, reset, set_item

    reset()
    set_item("jobs:ada", ["j1"], ttl_sec=10, now=100)
    assert get_item("jobs:ada", now=105) == ["j1"]
    assert get_item("jobs:ada", now=111) is None


def test_batch_db_writes_for_ingestion_and_logs():
    from app.batch_writes import flush_batches

    seen: list[int] = []
    result = flush_batches([{"id": i} for i in range(12)], size=5, writer=lambda batch: seen.append(len(batch)))
    assert result["batches"] == 3
    assert result["written"] == 12
    assert seen == [5, 5, 2]


def test_workday_adapter_v1_fixture_only(monkeypatch):
    from app.job_sources.boards import workday_jobs

    payload = json.loads((FIXTURES / "job_boards" / "workday.json").read_text())
    monkeypatch.setenv("FLAG_WORKDAY_ADAPTER", "false")
    get_settings.cache_clear()
    assert workday_jobs(payload, listing_url="https://fixtures.ajas.local/workday") == []
    monkeypatch.setenv("FLAG_WORKDAY_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = workday_jobs(payload, listing_url="https://fixtures.ajas.local/workday")
    assert rows[0]["source_posting_id"] == "wd-1"
    assert rows[0]["title"] == "Staff Data Engineer"


def test_ziprecruiter_adapter_v1_fixture_throttling(monkeypatch):
    from app.job_sources.boards import backoff_seconds, ziprecruiter_jobs

    payload = json.loads((FIXTURES / "job_boards" / "ziprecruiter.json").read_text())
    monkeypatch.setenv("FLAG_ZIPRECRUITER_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = ziprecruiter_jobs(payload, listing_url="https://fixtures.ajas.local/ziprecruiter")
    assert [row["source_posting_id"] for row in rows] == ["zr-1", "zr-2"]
    assert backoff_seconds(2) == 1.0
    monkeypatch.setenv("FLAG_ZIPRECRUITER_ADAPTER", "false")
    get_settings.cache_clear()
    assert ziprecruiter_jobs(payload) == []


def test_proxy_rotation_pool_health_checks():
    from app.job_sources.proxies import add, next_proxy, record_result, reset, snapshot

    reset()
    add("https://proxy-a.ajas.local:8443")
    add("https://proxy-b.ajas.local:8443")
    first = next_proxy()
    second = next_proxy()
    assert first and second and first.url != second.url
    record_result(first.url, False)
    record_result(first.url, False)
    record_result(first.url, False)
    snap = snapshot()
    assert snap["healthy"] == 1
    assert first.url not in snap["urls"]


def test_captcha_detection_hitl_stub_never_bypasses():
    from app.auto_apply.captcha import apply_gate, detect

    blocked = detect("<div class='g-recaptcha'></div>")
    assert blocked["captcha"] is True
    assert blocked["action"] == "needs_manual"
    assert blocked["bypass"] is False
    assert apply_gate("thanks for applying") == "continue"


def test_source_change_detection_dom_api_drift():
    from app.job_sources.drift import detect_change, reset

    reset()
    first = detect_change("workday", {"jobs": [{"id": "1", "title": "A"}]})
    second = detect_change("workday", {"jobs": [{"id": "1", "title": "A"}]})
    third = detect_change("workday", {"jobs": [{"id": "1", "title": "A", "salary": "100k"}]})
    assert first["firstSeen"] is True
    assert second["changed"] is False
    assert third["changed"] is True


def test_dpia_robots_policy_doc_exists():
    doc = Path(__file__).resolve().parents[2] / "docs" / "ops" / "dpia-robots.md"
    text = doc.read_text()
    assert "FLAG_RESPECT_ROBOTS" in text
    assert "fixture-only" in text.lower() or "Fixture-only" in text


def test_certification_extractor_v2_patterns():
    from app.resumes.certs import extract_certs

    found = extract_certs("AWS Certified Solutions Architect and CKA. Also CISSP.")
    families = {item["family"] for item in found}
    assert "aws" in families
    assert "kubernetes" in families
    assert "security" in families


def test_education_normalization_v2_degrees_schools():
    from app.resumes.education import normalize_education

    row = normalize_education("M.S. in Computer Science, MIT")
    assert row["degree"] == "master"
    assert row["school"] == "Massachusetts Institute of Technology"
    assert row["major"] == "Computer Science"


def test_experience_timeline_rebuild_infers_gaps():
    from app.resumes.timeline import rebuild_timeline

    rebuilt = rebuild_timeline(
        [
            "Engineer at Acme Jan 2018 - Dec 2019",
            "Staff at Globex Jun 2021 - Present",
        ]
    )
    assert rebuilt["count"] == 2
    assert rebuilt["gaps"]


def test_multilingual_parsing_en_es_fr():
    from app.resumes.multilingual import detect_lang, parse_branch

    assert detect_lang("Experience and education skills in python") == "en"
    assert detect_lang("experiencia laboral y habilidades técnicas") == "es"
    assert detect_lang("expérience professionnelle et compétences") == "fr"
    assert parse_branch("education and skills")["parser"] == "resume.en"


def test_seniority_mapping_includes_lead_staff_principal():
    from app.job_sources.enrich import infer_seniority
    from app.matching.boosts import seniority_level

    assert seniority_level("Lead Engineer") == 5
    assert seniority_level("Staff Engineer") == 5
    assert seniority_level("Principal Engineer") == 6
    assert infer_seniority("Lead Platform Engineer")["label"] == "lead"
    assert infer_seniority("Staff Platform Engineer")["label"] == "staff"


def test_location_radius_boosts_distance_aware():
    from app.matching.radius import radius_boost

    close = radius_boost("Seattle", "Seattle", resume_state="WA", job_state="WA")
    far = radius_boost("Seattle", "Austin", resume_state="WA", job_state="TX")
    assert close["within"] is True
    assert close["boost"] >= far["boost"]
    assert far["km"] > 100


def test_visa_work_auth_country_rules():
    from app.matching.visa import visa_rules

    us = visa_rules("US citizen required", "Canadian citizen", country="US")
    sponsor = visa_rules("H1B visa sponsorship", "needs visa sponsorship", country="US")
    assert us["boost"] < 0
    assert "citizen_only" in us["flags"]
    assert sponsor["boost"] > 0


def test_cross_encoder_rerank_stage():
    from app.matching.rerank import rerank

    ranked = rerank(
        [
            {"id": "a", "resume": "python azure kubernetes", "job": "java cobol"},
            {"id": "b", "resume": "python azure kubernetes", "job": "python azure"},
        ]
    )
    assert ranked[0]["id"] == "b"
    assert ranked[0]["rerank"] > ranked[1]["rerank"]


def test_ab_framework_ranking_buckets_and_metrics():
    from app.matching.ab import assign_variant, record, reset_metrics, snapshot

    reset_metrics()
    bucket = assign_variant("ada")
    assert bucket in {"kw30", "balanced"}
    assert assign_variant("ada") == bucket
    record(bucket, approved=True)
    record(bucket, approved=False)
    stats = snapshot()[bucket]
    assert stats["shown"] == 2
    assert stats["approved"] == 1


def test_active_learning_hooks_queue_uncertain_scores():
    from app.matching.active_learning import drain, enqueue, snapshot, uncertain

    assert uncertain(60) is True
    assert uncertain(90) is False
    enqueue({"matchId": "m1"}, score=58)
    assert snapshot()["queued"] == 1
    assert drain()[0]["matchId"] == "m1"


def test_feedback_thumbs_up_down_store():
    from app.matching.feedback import record, reset, summary

    reset()
    record(user_id="ada", match_id="m1", thumb="up")
    record(user_id="ada", match_id="m1", thumb="down")
    assert summary()["up"] == 1
    assert summary()["down"] == 1


def test_apply_screenshots_capture_submit_steps():
    from app.auto_apply.screenshots import capture_step, for_request, reset

    reset()
    capture_step("req-1", "open-form")
    capture_step("req-1", "submit")
    assert [step["name"] for step in for_request("req-1")] == ["open-form", "submit"]


def test_gmail_oauth_hardening_refresh_and_scopes():
    from app.mail.oauth_hardening import classify_oauth_error, required_scopes

    assert "Mail.Send" in required_scopes()
    assert classify_oauth_error(401, "invalid_grant")["code"] == "refresh_required"
    assert classify_oauth_error(403, "insufficient scopes")["retry"] is False
    assert classify_oauth_error(503)["retry"] is True


def test_outlook_graph_transport_not_imap():
    from app.mail.outlook import outlook_status

    status = outlook_status()
    assert status["provider"] == "microsoft-graph"
    assert status["imap"] is False
    assert status["smtp"] is False
    assert status["graph"] is True


def test_pii_redaction_review_payloads():
    from app.privacy_review import has_raw_pii, review_payload

    cleaned = review_payload({"email": "ada@contoso.com", "card": "4111 1111 1111 1111"})
    assert "ada@contoso.com" not in str(cleaned)
    assert "[redacted" in str(cleaned)
    assert has_raw_pii("ada@contoso.com") is True


def test_rbac_owner_admin_user_gates():
    from app.auth import Principal
    from app.rbac import ROLE_OWNER, permissions_payload, role_for_principal

    owner = Principal(user_id="local-owner", scopes=frozenset({"owner"}))
    admin = Principal(user_id="local-admin", scopes=frozenset({"admin"}))
    user = Principal(user_id="ada", scopes=frozenset())
    assert role_for_principal(owner) == ROLE_OWNER
    assert permissions_payload(owner)["permissions"]["purge"] is True
    assert permissions_payload(admin)["permissions"]["ops"] is True
    assert permissions_payload(user)["permissions"]["ops"] is False


def test_retention_executor_scheduled_purge():
    from app.retention_exec import run_scheduled

    result = run_scheduled(jobs=[], emails=[])
    assert result["scheduled"] is True
    assert "plan" in result


def test_slo_ingest_match_apply_error_budgets():
    from app.slo_pipelines import record, reset, snapshot

    reset()
    record("ingest", ok=True)
    record("match", ok=True)
    record("apply", ok=False)
    rows = {item["pipeline"]: item for item in snapshot()}
    assert rows["ingest"]["healthy"] is True
    assert rows["apply"]["err"] == 1


def test_settings_automation_limits_consent_and_caps():
    from app.auto_apply.limits import allow, reset, set_consent

    reset()
    assert allow("greenhouse")["reason"] == "consent"
    set_consent("greenhouse", True)
    assert allow("greenhouse", cap=1)["allowed"] is True
    assert allow("greenhouse", cap=1)["reason"] == "cap"


def test_slack_alert_hooks_slo_payload():
    from app.slack_alerts import should_notify, slack_payload

    alert = {"route": "ingest", "p95Ms": 9000, "budgetMs": 8000, "ok": False}
    payload = slack_payload(alert)
    assert "SLO breach" in payload["text"]
    assert should_notify(alert) is True


def test_source_quotas_dashboard_counters():
    from app.source_quotas import dashboard, record, reset

    reset()
    record("workday", fetched=2, capped=1)
    rows = {item["source"]: item for item in dashboard()}
    assert rows["workday"]["fetched"] == 2
    assert rows["workday"]["capHit"] is True


def test_db_indices_hot_paths_matches_logs():
    from app.db_indices import index_policy

    paths = {item["path"] for item in index_policy()["includedPaths"]}
    assert "/userId" in paths
    assert "/traceId" in paths


def test_model_usage_budgets_cost_guardrails():
    from app.model_budget import consume, reset

    reset()
    ok = consume("ada", 100)
    blocked = consume("ada", 80_000)
    assert ok["allowed"] is True
    assert blocked["allowed"] is False


def test_email_threading_v2_reliable_ids():
    from app.mail.threading_v2 import thread_id

    assert thread_id(conversation_id="AAMk") == "graph:AAMk"
    assert thread_id(in_reply_to="<abc@mail>") == "rfc:abc@mail"
    assert thread_id(message_id="<own@mail>") == "rfc:own@mail"

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

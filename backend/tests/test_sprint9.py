"""Sprint 9: matching evidence/boosts, enrichment, email intent, flags, retention."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import azure.functions as func
import pytest

from app.auto_apply.attachments import POLICY, validate_attachment
from app.auto_apply.cover import canned_cover_letter
from app.auto_apply.errors import AutoApplyValidationError
from app.auto_apply.models import AutoApplyAttempt
from app.config import get_settings
from app.flags import feature_enabled, feature_flags
from app.job_sources.boards import indeed_jobs, linkedin_jobs
from app.job_sources.enrich import clean_job_description, enrich_posting, fuzzy_duplicate, parse_salary
from app.job_sources.keys import utc_now
from app.mail.followup import recommend_followup
from app.mail.imap_health import imap_health
from app.mail.intent import classify_email
from app.mail.templates import recruiter_templates
from app.matching.boosts import apply_gate, fit_bucket, rule_boosts, skill_gate
from app.matching.embedder import HashEmbedder
from app.matching.evidence import evidence_sentences
from app.matching.explain import HeuristicExplainer
from app.matching.memory import InMemoryMatchingStore
from app.matching.queues import InMemoryJobQueue
from app.matching.runtime import set_service
from app.matching.service import MatchingService
from app.matching.taxonomy import expand_terms, rebuild_taxonomy
from app.matching.texts import MemoryTextLoader
from app.resumes.parser import HeuristicResumeParser
from app.retention import is_stale, plan_purge

FIXTURES = Path(__file__).parent / "fixtures"
RESUME = (
    "Staff Platform Engineer in Remote. Skills: python azure kubernetes terraform. "
    "Open to visa sponsorship discussions for H1B."
)
JOB = (
    "Title: Staff Platform Engineer\nCompany: Acme\nLocation: Remote\n"
    "Required: python kubernetes azure\nNice to have: golang kafka\n"
    "Build ingestion and matching pipelines in python on azure kubernetes. "
    "Compensation $180,000 to $210,000."
)


def _req(method: str, url: str, *, headers=None, params=None, body=None, route_params=None):
    payload = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    return func.HttpRequest(
        method=method,
        url=url,
        headers=headers or {"Authorization": "Bearer local-user"},
        params=params or {},
        route_params=route_params or {},
        body=payload,
    )


@pytest.fixture
def matching_svc(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = MatchingService(
        store=InMemoryMatchingStore(),
        queue=InMemoryJobQueue(),
        embedder=HashEmbedder(),
        explainer=HeuristicExplainer(),
        text_loader=MemoryTextLoader(),
    )
    set_service(service)
    try:
        yield service
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_evidence_and_explanation_summary(matching_svc):
    status, body = matching_svc.compute(
        "user-1",
        {"resumeText": RESUME, "jobText": JOB, "explanation": True, "threshold": 0},
    )
    assert status == 200
    assert body["explanation"]
    assert len(body["explanation"]) <= 500
    assert "Matched skills" in body["explanation"] or "Gaps" in body["explanation"]
    assert len(body["evidence"]) >= 1
    assert body["bucket"]["key"] in {"excellent", "strong", "promising", "fair", "poor"}
    assert body["gate"]["coverage"] >= 0.5
    assert "python" in body["highlights"] or "python" in body["gate"]["matchedRequired"]


def test_must_have_gating_caps_score():
    gate = skill_gate("python baker", "Required: rust golang\nNice to have: python")
    assert gate.missing_required
    assert apply_gate(88, gate) <= 54
    # Body paragraphs after Required: are not extra must-haves.
    prose = skill_gate(
        "Staff python azure kubernetes",
        "Required: python kubernetes azure\nBuild ingestion pipelines in python on azure kubernetes.",
    )
    assert prose.required == ["python", "kubernet", "azure"]
    assert prose.coverage == 1.0
    live = skill_gate(
        RESUME,
        "Title: Staff Platform Engineer\nRequired: python kubernetes azure\n"
        "Build python matching on azure kubernetes.\nVisa sponsorship available.\n"
        "Compensation $180,000 to $210,000.",
    )
    assert live.required == ["python", "kubernet", "azure"]
    assert live.coverage == 1.0
    bullets = skill_gate(
        "python kubernetes terraform",
        "Required:\n- Python\n- Kubernetes\n- Terraform\nWe also value communication.",
    )
    assert bullets.required == ["python", "kubernet", "terraform"]
    assert bullets.coverage == 1.0


def test_rule_boosts_location_seniority_visa():
    boosts = rule_boosts(
        "Staff engineer remote. Open to H1B visa sponsorship.",
        "Title: Staff Engineer\nLocation: Remote\nWe offer visa sponsorship.",
    )
    assert boosts.location > 0
    assert boosts.seniority > 0
    assert boosts.visa > 0
    assert fit_bucket(91)["key"] == "excellent"


def test_taxonomy_expands_k8s():
    assert "kubernetes" in expand_terms(["k8s"])
    dump = rebuild_taxonomy()
    assert dump["version"] == "taxonomy-s9-v1"


def test_ltr_features_logged(matching_svc):
    _status, body = matching_svc.compute(
        "user-1",
        {"resumeText": RESUME, "jobText": JOB, "explanation": False, "threshold": 0},
    )
    assert "keyword" in body["features"]
    assert "must_have_coverage" in body["features"]


def test_jd_cleaner_and_salary_and_fuzzy():
    dirty = "Build APIs.\n\nBenefits:\nUnlimited snacks\nEEO: we are an equal opportunity employer."
    assert "snacks" not in clean_job_description(dirty)
    salary = parse_salary("Compensation $120,000-$150,000")
    assert salary["min"] == 120000
    assert salary["max"] == 150000
    extra = enrich_posting(title="Senior Engineer", company="Acme", location="Remote", body=JOB)
    assert extra["workplace"] == "remote"
    assert extra["seniority"] == "staff"
    assert fuzzy_duplicate("Staff Engineer", "Acme Inc", "Staff Engineer", "Acme Inc")
    assert not fuzzy_duplicate("Baker", "Cakes", "Staff Engineer", "Acme")


def test_indeed_linkedin_fixtures_respect_flags(monkeypatch):
    payload = json.loads((FIXTURES / "job_boards" / "indeed.json").read_text())
    monkeypatch.setenv("FLAG_INDEED_ADAPTER", "true")
    monkeypatch.setenv("FLAG_SITE_POLICY_CONSENT", "true")
    get_settings.cache_clear()
    from app.job_sources import boards as boards_mod

    monkeypatch.setattr(boards_mod, "can_fetch", lambda target, parser=None, respect=None: True)
    rows = indeed_jobs(payload, listing_url="https://fixtures.ajas.local/indeed")
    assert rows and rows[0]["title"]
    monkeypatch.setenv("FLAG_INDEED_ADAPTER", "false")
    get_settings.cache_clear()
    assert indeed_jobs(payload) == []
    linked = json.loads((FIXTURES / "job_boards" / "linkedin.json").read_text())
    monkeypatch.setenv("FLAG_LINKEDIN_ADAPTER", "true")
    get_settings.cache_clear()
    assert linkedin_jobs(linked)


def test_email_intent_followup_and_templates():
    interview = classify_email(subject="Interview availability", body="Can we schedule a phone screen?")
    assert interview["intent"] == "interview"
    reject = classify_email(subject="Update", body="Unfortunately we are not moving forward.")
    assert reject["intent"] == "rejection"
    follow = recommend_followup(subject="Interview", body="loop next week")
    assert follow["windowHours"] == 4
    templates = recruiter_templates(first_name="Maya", company="Acme", role="Staff Engineer", job_ref="JOB-1")
    ids = {item["id"] for item in templates}
    assert {"interested", "not_fit", "schedule"} <= ids


def test_imap_health_is_graph_only():
    body = imap_health()
    assert body["transport"] == "graph"
    assert body["imapConfigured"] is False


def test_attachment_policy_and_cover_from_explanation():
    validate_attachment(kind="resume", content_type="application/pdf", size=1000)
    with pytest.raises(AutoApplyValidationError):
        validate_attachment(kind="resume", content_type="image/png", size=10)
    assert POLICY["resume"]["maxBytes"] == 5 * 1024 * 1024
    attempt = AutoApplyAttempt(
        user_id="u",
        vendor="greenhouse",
        created_at=utc_now(),
        updated_at=utc_now(),
        job_id="staff",
        posting_url="https://boards.greenhouse.io/acme/jobs/1",
    )
    letter = canned_cover_letter(attempt, {"full_name": "Jane Doe"}, explanation="Matched skills: python, azure.")
    assert "python" in letter


def test_retention_plan_and_flags(monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    assert is_stale(old, days=120)
    plan = plan_purge(
        jobs=[{"id": "j1", "updated_at": old}],
        emails=[{"id": "e1", "received_at": old}],
        job_days=30,
        mail_days=30,
    )
    assert "j1" in plan["jobIds"]
    monkeypatch.setenv("FLAG_BULK_AUTO_APPLY", "false")
    get_settings.cache_clear()
    assert feature_enabled("bulk_auto_apply") is False
    assert "indeed_adapter" in feature_flags()


def test_resume_parser_extracts_experience_education():
    parsed = HeuristicResumeParser().parse(
        resume_id="r1",
        text="Skills: python, azure\nExperience: Staff Engineer at Acme\nEducation: BSc Computer Science\nCertifications: AWS",
    )
    assert any(skill.name.lower() == "python" for skill in parsed.skills)
    assert parsed.experiences
    assert parsed.educations


def test_health_includes_workers(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    from app.features.health import health, ready

    body = json.loads(health(_req("GET", "http://localhost/api/health")).get_body())
    assert "workers" in body
    assert body["workers"]["match"] is True
    ready_body = json.loads(ready(_req("GET", "http://localhost/api/ready")).get_body())
    assert ready_body["ready"] is True
    assert "flags" in ready_body


def test_ingestion_match_apply_happy_path(matching_svc):
    from app.auto_apply.blobs import InMemoryBlobStore
    from app.auto_apply.memory import InMemoryAutoApplyStore
    from app.auto_apply.queues import InMemoryJobQueue as ApplyQueue
    from app.auto_apply.runtime import set_service as set_apply
    from app.auto_apply.service import AutoApplyService

    apply_svc = AutoApplyService(store=InMemoryAutoApplyStore(), queue=ApplyQueue(), blobs=InMemoryBlobStore())
    set_apply(apply_svc)
    try:
        status, match = matching_svc.compute(
            "user-1",
            {"resumeText": RESUME, "jobText": JOB, "explanation": True, "threshold": 0},
        )
        assert status == 200
        created_status, created = apply_svc.create_request(
            "user-1",
            {
                "job_source": "greenhouse",
                "job_posting_id": "job-staff",
                "posting_url": "https://boards.greenhouse.io/acme/jobs/staff",
                "resume_id": "resume-1",
                "cover_letter_mode": "generate",
                "consent_approved": True,
                "match_explanation": match["explanation"],
            },
        )
        assert created_status == 201
        detail = apply_svc.get_request("user-1", created["request_id"])
        assert detail["attachment_policy"]["resume"]["required"] is True
        assert "python" in (detail.get("cover_letter_text") or "")
    finally:
        set_apply(None)


def test_retry_and_partial_failure(matching_svc):
    from app.auto_apply.validation import retry_backoff_seconds

    assert retry_backoff_seconds(1) >= 2
    _status, body = matching_svc.rank(
        "user-1",
        {
            "resumeText": RESUME,
            "jobTexts": [JOB, "Title: Baker\nSkills: frosting"],
            "explanation": True,
            "threshold": 0,
        },
    )
    assert len(body["results"]) == 2
    scores = [row["score"] for row in body["results"]]
    assert scores[0] >= scores[1]

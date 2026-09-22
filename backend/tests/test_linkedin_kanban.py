"""Kanban: LinkedIn field map, pagination, rate limits, session, Easy Apply gaps."""

from __future__ import annotations

import json
from pathlib import Path

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import integrations as routes
from app.flags import feature_flags
from app.integrations import easy_apply as ea
from app.integrations import linkedin_audit
from app.integrations import linkedin_session
from app.integrations.ingest import classify_error, linkedin_ingest, reset_limiter, retry_with_backoff, throttle
from app.integrations.linkedin_metrics import evaluate, qa_acceptance
from app.integrations.linkedin_spec import (
    ATTACHMENT_SPEC,
    EASY_APPLY_FIELDS,
    ERROR_MATRIX,
    FIELD_MAP,
    PAGINATION,
    PRD_GAPS_EASY_APPLY,
    PRD_GAPS_INGEST,
    RATE_PLAN,
    SUCCESS_TARGETS,
    classify_field_error,
    counters,
    detect_challenge,
    evaluate_security,
    listing_dedupe_key,
    map_linkedin_job,
    render_cover_letter,
    spec_bundle,
    walk_pages,
)
from app.integrations.pipeline import run_linkedin_e2e
from app.integrations.service import reset_service
from app.job_sources.circuit import record_status, reset as reset_circuit
from app.job_sources.constants import SOURCE_TYPES

FIXTURES = Path(__file__).parent / "fixtures" / "job_boards"
USER = "user-1"
RESUME = {
    "kind": "resume",
    "name": "resume.pdf",
    "contentType": "application/pdf",
    "data": b"%PDF-1.4 cv",
}
PROFILE = {
    "full_name": "Alex Jobseeker",
    "email": "alex@ajas.dev",
    "phone": "555-0100",
    "linkedin_url": "https://www.linkedin.com/in/alex",
}


def _req(method: str, url: str, *, params=None, body=None, route_params=None, auth=True):
    headers = {"Authorization": f"Bearer {USER}"} if auth else {}
    payload = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    return func.HttpRequest(
        method=method,
        url=url,
        headers=headers,
        params=params or {},
        route_params=route_params or {},
        body=payload,
    )


def _enable(monkeypatch, **flags: bool) -> None:
    mapping = {
        "linkedin": "FLAG_LINKEDIN_ADAPTER",
        "easy": "FLAG_LINKEDIN_EASY_APPLY",
        "consent": "FLAG_SITE_POLICY_CONSENT",
    }
    for key, env in mapping.items():
        monkeypatch.setenv(env, "true" if flags.get(key, False) else "false")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clean():
    reset_service()
    reset_limiter()
    reset_circuit()
    linkedin_session.reset()
    linkedin_audit.reset()
    ea.reset()
    get_settings.cache_clear()
    yield
    reset_service()
    reset_limiter()
    reset_circuit()
    linkedin_session.reset()
    linkedin_audit.reset()
    ea.reset()
    get_settings.cache_clear()


def test_field_mapping_table_is_source_of_truth():
    internals = {row["internal"] for row in FIELD_MAP}
    assert {"sourcePostingId", "title", "company", "location", "description", "postingUrl", "postedAt", "visibility"} <= internals
    for row in FIELD_MAP:
        assert row["type"]
        assert "nullable" in row
        assert "fallback" in row
        assert row["linkedin"]
    raw = {
        "jobTitle": "Staff Platform Engineer",
        "companyName": "Initech",
        "formattedLocation": "Remote",
        "jobDescription": "Python azure.",
        "url": "https://fixtures.ajas.local/linkedin/x",
        "datePosted": "2026-09-01T12:00:00Z",
        "entityUrn": "urn:li:job:99",
    }
    mapped = map_linkedin_job(raw)
    assert mapped["title"] == "Staff Platform Engineer"
    assert mapped["company"] == "Initech"
    assert mapped["location"] == "Remote"
    assert mapped["description"].startswith("Python")
    assert mapped["postingUrl"].endswith("/x")
    assert mapped["postedAt"] == "2026-09-01T12:00:00Z"
    assert mapped["sourcePostingId"] == "urn:li:job:99"
    assert mapped["listingKey"] == listing_dedupe_key(
        title="Staff Platform Engineer",
        company="Initech",
        location="Remote",
        posted_at="2026-09-01T12:00:00Z",
    )


def test_rate_plan_has_thresholds_jitter_circuit_and_counters(monkeypatch):
    _enable(monkeypatch, linkedin=True)
    plan = RATE_PLAN["ingest"]
    assert plan["capPerWindow"] == 50
    assert plan["jitterSeconds"] > 0
    assert plan["maxAttempts"] == 4
    assert plan["circuitFailureThreshold"] == 5
    assert plan["circuitOpenSeconds"] == 300
    assert 429 in plan["retryStatus"]
    reset_limiter()
    first = throttle("linkedin", cap=2)
    second = throttle("linkedin", cap=2)
    blocked = throttle("linkedin", cap=2)
    assert first["allowed"] and second["allowed"]
    assert blocked["allowed"] is False
    retry = retry_with_backoff([429, 503, 200], jitter=0.0)
    assert retry["retried"] is True
    assert retry["attempts"][-1]["class"] == "ok"
    assert counters()["retries"] >= 2
    assert counters()["rate_limited"] >= 1
    record_status("linkedin", 503)
    record_status("linkedin", 503)
    record_status("linkedin", 503)
    record_status("linkedin", 503)
    snap = record_status("linkedin", 503)
    assert snap.open is True
    out = linkedin_ingest({"jobs": [{"title": "A", "company": "B", "apply_url": "https://fixtures.ajas.local/x"}]})
    assert out["reason"] == "circuit_open"
    assert counters()["circuit_open"] >= 1


def test_pagination_cursor_stop_and_dedupe_by_listing_key(monkeypatch):
    _enable(monkeypatch, linkedin=True)
    payload = json.loads((FIXTURES / "linkedin_pages.json").read_text())
    walked = walk_pages(payload)
    assert walked["cursors"] == ["c1", "c2"]
    assert walked["stop"] == "no_next_cursor"
    assert PAGINATION["mode"] == "cursor"
    assert "duplicate_cursor" in PAGINATION["stop"]
    dup_walk = walk_pages(
        {
            "pages": [
                {"cursor": "c1", "jobs": [{"title": "A"}], "nextCursor": "c1"},
                {"cursor": "c1", "jobs": [{"title": "B"}], "nextCursor": None},
            ]
        }
    )
    assert dup_walk["stop"] == "duplicate_cursor"
    out = linkedin_ingest(payload)
    assert out["reason"] == "ok"
    assert out["pagination"]["mode"] == "cursor"
    titles = {job["title"] for job in out["jobs"]}
    assert "Staff Platform Engineer" in titles
    assert "Senior Backend Engineer" in titles
    assert "Secret Staff Role" not in titles
    assert "Expired Backend Role" not in titles
    assert out["metrics"]["privateSkipped"] == 1
    assert out["metrics"]["expiredSkipped"] == 1
    # same title+company+location+postedAt on page 2 is a duplicate despite tracking URL
    staff = [job for job in out["jobs"] if job["title"] == "Staff Platform Engineer"]
    assert len(staff) == 1
    assert out["metrics"]["deduped"] >= 1
    assert all(job.get("postedAt") is not None for job in out["jobs"])
    assert all(job.get("listingKey") for job in out["jobs"])


def test_session_lifecycle_refresh_multi_account_rotation_sealed():
    store = linkedin_session.STORE
    first = store.put("acct-a", "li_at_secret_aaa", ttl_seconds=3600)
    assert first["status"] == "active"
    assert "token" not in first
    assert "cipher" not in first
    assert first["tokenHash"]
    unlocked = store.unlock("acct-a")
    assert unlocked == "li_at_secret_aaa"
    public = store.public("acct-a")
    assert "li_at_secret_aaa" not in str(public)
    second = store.put("acct-b", "li_at_secret_bbb")
    assert second["accountId"] == "acct-b"
    assert len(store.list_accounts()) == 2
    rotated = store.rotate("acct-a", "li_at_secret_ccc")
    assert rotated["version"] == 2
    assert store.unlock("acct-a") == "li_at_secret_ccc"
    refreshed = store.refresh("acct-b")
    assert refreshed["version"] >= 2
    expired = store.put("acct-c", "short", ttl_seconds=0)
    assert expired["status"] in {"expired", "expiring"}
    with pytest.raises(ValueError):
        store.put("acct-d", "nope")  # max 3 accounts
    revoked = store.revoke("acct-b")
    assert revoked["status"] == "revoked"
    with pytest.raises(ValueError):
        store.unlock("acct-b")


def test_easy_apply_validation_error_matrix_and_remediation(monkeypatch):
    _enable(monkeypatch, linkedin=True, easy=True)
    job = {"id": "j1", "title": "Staff", "company": "Globex", "postingUrl": "https://fixtures.ajas.local/linkedin/j1"}
    missing = ea.submit(job=job, profile={"full_name": "Alex"}, attachments=[RESUME])
    assert missing["code"] == "MISSING_REQUIRED"
    assert missing["userPrompt"]
    assert missing["receipt"]["status"] == "failed"
    bad_email = ea.submit(job=job, profile={**PROFILE, "email": "not-an-email"}, attachments=[RESUME])
    assert bad_email["code"] == "INVALID_EMAIL"
    bad_phone = ea.submit(job=job, profile={**PROFILE, "phone": "12"}, attachments=[RESUME])
    assert bad_phone["code"] == "INVALID_PHONE"
    bad_url = ea.submit(job=job, profile={**PROFILE, "linkedin_url": "https://example.com/me"}, attachments=[RESUME])
    assert bad_url["code"] == "INVALID_LINKEDIN_URL"
    no_resume = ea.submit(job=job, profile=PROFILE, attachments=[])
    assert no_resume["code"] == "MISSING_RESUME"
    bad_type = ea.submit(
        job=job,
        profile=PROFILE,
        attachments=[{"kind": "resume", "name": "x.exe", "contentType": "application/octet-stream", "data": b"xx"}],
    )
    assert bad_type["code"] == "ATTACHMENT_TYPE"
    too_big = ea.submit(
        job=job,
        profile=PROFILE,
        attachments=[{"kind": "resume", "name": "x.pdf", "contentType": "application/pdf", "size": 6 * 1024 * 1024, "data": b"%PDF"}],
    )
    assert too_big["code"] == "ATTACHMENT_SIZE"
    private = ea.submit(job={**job, "private": True}, profile=PROFILE, attachments=[RESUME])
    assert private["code"] == "PRIVATE_JOB"
    expired = ea.submit(job={**job, "expired": True}, profile=PROFILE, attachments=[RESUME])
    assert expired["code"] == "EXPIRED_JOB"
    assert classify_field_error(PROFILE, [RESUME]) is None
    required = [row["profile"] for row in EASY_APPLY_FIELDS if row["required"]]
    assert required == ["full_name", "email", "resume"]
    assert set(ERROR_MATRIX) >= {"MISSING_REQUIRED", "CAPTCHA", "TIMEOUT", "RATE_LIMIT"}


def test_attachment_spec_cover_template_and_profile_map(monkeypatch):
    _enable(monkeypatch, linkedin=True, easy=True)
    assert ATTACHMENT_SPEC["resume"]["required"] is True
    assert ATTACHMENT_SPEC["coverLetter"]["required"] is False
    assert ATTACHMENT_SPEC["resume"]["maxBytes"] == 5 * 1024 * 1024
    job = {
        "id": "j2",
        "title": "Staff Engineer",
        "company": "Globex",
        "location": "Austin, TX",
        "postingUrl": "https://fixtures.ajas.local/linkedin/j2",
    }
    letter = render_cover_letter(job=job, profile=PROFILE)
    assert "Globex" in letter and "Staff Engineer" in letter and "Alex Jobseeker" in letter
    result = ea.submit(
        job=job,
        profile={**PROFILE, "cover_letter_mode": "generate"},
        attachments=[RESUME],
        questions=[{"key": "work_authorization"}],
    )
    assert result["status"] == "submitted"
    assert "cover.txt" in result["receipt"]["attachments"]
    assert result["receipt"]["fieldsSent"]["name"] == "Alex Jobseeker"
    assert result["receipt"]["fieldsSent"]["email"] == "alex@ajas.dev"
    assert result["receipt"]["answers"]["work_authorization"]


def test_audit_telemetry_redacts_pii(monkeypatch):
    _enable(monkeypatch, linkedin=True, easy=True)
    linkedin_ingest(json.loads((FIXTURES / "linkedin.json").read_text()))
    ea.submit(
        job={"id": "j3", "title": "Staff", "company": "Globex", "postingUrl": "https://fixtures.ajas.local/linkedin/j3"},
        profile=PROFILE,
        attachments=[RESUME],
    )
    rows = linkedin_audit.events()
    assert any(row["event"] == "fetch" for row in rows)
    assert any(row["event"] == "submitted" for row in rows)
    for row in rows:
        assert linkedin_audit.assert_pii_safe(row)
        assert "alex@ajas.dev" not in str(row)
        assert "555-0100" not in str(row)
        leaked = linkedin_audit.record("apply", email="alex@ajas.dev", token="li_at_secret", phone="555-0100")
        assert "email" not in leaked
        assert "token" not in leaked
        assert linkedin_audit.assert_pii_safe(leaked)


def test_captcha_challenge_timeout_never_bypass(monkeypatch):
    _enable(monkeypatch, linkedin=True, easy=True)
    job = {"id": "j4", "title": "Staff", "company": "Globex", "postingUrl": "https://fixtures.ajas.local/linkedin/j4"}
    captcha = ea.submit(job=job, profile=PROFILE, attachments=[RESUME], page="<div class='g-recaptcha'></div>")
    assert captcha["status"] == "needs_manual"
    assert captcha["bypass"] is False
    assert captcha["abort"] is True
    assert captcha["userPrompt"]
    assert detect_challenge(captcha)["bypass"] is False or captcha["code"] == "CAPTCHA"
    challenge = ea.submit(job=job, profile=PROFILE, attachments=[RESUME], page="unusual activity checkpoint")
    assert challenge["status"] == "needs_manual"
    assert challenge["code"] == "CHALLENGE"
    assert challenge["bypass"] is False
    timeout = ea.submit(job=job, profile=PROFILE, attachments=[RESUME], page="request timeout from gateway")
    assert timeout["status"] == "failed"
    assert timeout["code"] == "TIMEOUT"
    assert timeout["retry"]["retried"] is True
    assert classify_error(200, "<div class='hcaptcha'></div>")["bypass"] is False


def test_security_checklist_and_qa_metrics(monkeypatch):
    flags = feature_flags()
    session = linkedin_session.STORE.put("acct-sec", "super-secret-token")
    linkedin_audit.record("fetch", ingested=1, email="should-drop@ajas.dev")
    security = evaluate_security(
        session_public=session,
        audit_rows=linkedin_audit.events(),
        flags=flags,
        source_types=SOURCE_TYPES,
    )
    assert security["passed"] is True
    assert security["items"]["data_minimization"]
    assert security["items"]["storage_encryption"]
    assert security["items"]["access_control"]
    assert security["items"]["redaction"]
    assert security["items"]["fail_closed"]
    sample = evaluate(
        {
            "ingested": 98,
            "updated": 0,
            "failed": 2,
            "skipped": 10,
            "duplicatesPresent": True,
            "submitted": 8,
            "applyAttempts": 10,
            "runtimesMs": [1200, 1800, 2400],
        }
    )
    assert sample["passed"] is True
    assert sample["measured"]["fetchSuccessPct"] >= SUCCESS_TARGETS["fetchSuccessPct"]
    qa = qa_acceptance(
        flags=flags,
        captcha_bypass=False,
        receipts=3,
        attempts=3,
        audit_safe=True,
    )
    assert qa["passed"] is True
    assert SOURCE_TYPES == frozenset({"greenhouse", "lever"})
    assert flags["linkedin_adapter"] is False
    assert flags["linkedin_easy_apply"] is False


def test_prd_gap_pass_contracts_encoded():
    bundle = spec_bundle()
    assert bundle["liveScrape"] is False
    assert bundle["prdGaps"]["jobsIngestion"] == list(PRD_GAPS_INGEST)
    assert bundle["prdGaps"]["easyApply"] == list(PRD_GAPS_EASY_APPLY)
    ingest_prd = Path("/workspace/prds/connectors/linkedin/jobs-ingestion-backend-prd.md").read_text()
    easy_prd = Path("/workspace/prds/connectors/linkedin/easy-apply-backend-prd.md").read_text()
    for needle in ("private", "expired", "rate", "pagination", "retry", "telemetry", "success"):
        assert needle.lower() in ingest_prd.lower()
    for needle in ("required", "validation", "resume", "cover", "timeout", "captcha", "autofill"):
        assert needle.lower() in easy_prd.lower()
    assert "linkedin.com/in/" in easy_prd
    assert bundle["attachments"]["resume"]["required"] is True


def test_http_spec_session_and_e2e_acceptance(monkeypatch):
    _enable(monkeypatch, linkedin=True, easy=True)
    denied = routes.integrations_linkedin_spec(_req("GET", "http://localhost/api/v1/integrations/linkedin/spec", auth=False))
    assert denied.status_code == 401
    spec = json.loads(routes.integrations_linkedin_spec(_req("GET", "http://localhost/api/v1/integrations/linkedin/spec")).get_body())
    assert spec["fieldMap"]
    assert spec["ratePlan"]["ingest"]["capPerWindow"] == 50
    assert spec["pagination"]["mode"] == "cursor"
    created = json.loads(
        routes.integrations_linkedin_session(
            _req("POST", "http://localhost/api/v1/integrations/linkedin/session", body={"accountId": "acct-http", "token": "li_at_http"})
        ).get_body()
    )
    assert created["status"] == "active"
    assert "token" not in created
    listed = json.loads(routes.integrations_linkedin_session(_req("GET", "http://localhost/api/v1/integrations/linkedin/session")).get_body())
    assert listed["accounts"]
    payload = json.loads((FIXTURES / "linkedin.json").read_text())
    result = run_linkedin_e2e(payload, resume_text="Staff python azure kubernetes", profile=PROFILE, attachments=[RESUME])
    assert result["ok"] is True
    assert result["applies"][0]["status"] == "submitted"
    assert result["applies"][0]["receipt"]["confirmation"].startswith("EA-")
    http_e2e = json.loads(
        routes.integrations_linkedin_e2e(
            _req("POST", "http://localhost/api/v1/integrations/linkedin/e2e", body={"payload": payload, "profile": PROFILE})
        ).get_body()
    )
    assert http_e2e["ok"] is True

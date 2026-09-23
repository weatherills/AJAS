"""Kanban integrations: Indeed, LinkedIn, Harvest, Gmail, Graph, Drive, Slack."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import azure.functions as func
import pytest
from pypdf import PdfWriter

from app.config import get_settings
from app.features import integrations as routes
from app.integrations.drive import LocalDriveClient, seed_pdf
from app.integrations.easy_apply import reset as reset_easy_apply
from app.integrations.gmail import LocalGmailClient, send_mail, sync_inbox
from app.integrations.harvest import list_applications, map_application
from app.integrations.ingest import (
    classify_error,
    detect_apply_method,
    glassdoor_ingest,
    indeed_ingest,
    linkedin_ingest,
    reset_limiter,
    retry_with_backoff,
    throttle,
)
from app.integrations.pipeline import run_linkedin_e2e
from app.integrations.scheduler import due, record_run, reset as reset_scheduler, tick
from app.integrations.search import parse_search
from app.integrations.service import reset_service
from app.integrations.slack import MemorySlackHttp, format_event, notify_event, post_webhook
from app.job_sources.circuit import reset as reset_circuit
from app.mail.graph import HttpGraphClient
from app.notify import reset as reset_notify
from app.resumes.blobs import InMemoryBlobStore
from app.resumes.memory import InMemoryResumeStore
from app.resumes.parser import HeuristicResumeParser
from app.resumes.queueing import InMemoryParseQueue
from app.resumes.service import ResumeService

FIXTURES = Path(__file__).parent / "fixtures" / "job_boards"
USER = "user-1"
RESUME_TEXT = (
    "Staff Platform Engineer. Skills: python azure kubernetes terraform. "
    "Remote. Authorized to work."
)


def _req(method: str, url: str, *, params=None, body=None, route_params=None):
    payload = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    return func.HttpRequest(
        method=method,
        url=url,
        headers={"Authorization": f"Bearer {USER}"},
        params=params or {},
        route_params=route_params or {},
        body=payload,
    )


def _pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _enable(monkeypatch, **flags: bool) -> None:
    mapping = {
        "indeed": "FLAG_INDEED_ADAPTER",
        "linkedin": "FLAG_LINKEDIN_ADAPTER",
        "glassdoor": "FLAG_GLASSDOOR_ADAPTER",
        "easy": "FLAG_LINKEDIN_EASY_APPLY",
        "harvest": "FLAG_GREENHOUSE_HARVEST",
        "gmail": "FLAG_GMAIL_ADAPTER",
        "drive": "FLAG_GOOGLE_DRIVE",
        "slack": "FLAG_SLACK_NOTIFY",
        "consent": "FLAG_SITE_POLICY_CONSENT",
    }
    for key, env in mapping.items():
        monkeypatch.setenv(env, "true" if flags.get(key, False) else "false")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    reset_service()
    reset_easy_apply()
    reset_scheduler()
    reset_circuit()
    reset_notify()
    get_settings.cache_clear()
    yield
    reset_service()
    reset_easy_apply()
    reset_scheduler()
    reset_circuit()
    reset_notify()
    get_settings.cache_clear()


def test_flags_default_off():
    from app.flags import feature_flags

    flags = feature_flags()
    assert flags["indeed_adapter"] is False
    assert flags["linkedin_adapter"] is False
    assert flags["glassdoor_adapter"] is False
    assert flags["linkedin_easy_apply"] is False
    assert flags["greenhouse_harvest"] is False
    assert flags["gmail_adapter"] is False
    assert flags["google_drive"] is False
    assert flags["slack_notify"] is False


def test_indeed_ingest_normalizes_dedupes_and_stores(monkeypatch):
    _enable(monkeypatch, indeed=True)
    payload = json.loads((FIXTURES / "indeed.json").read_text())
    first = indeed_ingest(payload, search={"keywords": "Platform", "limit": 10})
    assert first["reason"] == "ok"
    assert first["metrics"]["ingested"] == 1
    assert first["jobs"][0]["title"] == "Staff Platform Engineer"
    assert first["jobs"][0]["company"] == "Acme"
    assert first["jobs"][0]["postingUrl"]
    assert first["jobs"][0]["contentHash"]
    store = {row["id"]: row for row in first["jobs"]}
    seen = {f"{row['contentHash']}|{row['postingUrl']}": row for row in first["jobs"]}
    second = indeed_ingest(payload, store=store, seen=seen)
    assert second["metrics"]["ingested"] == 0
    assert second["metrics"]["skipped"] == 1
    empty = indeed_ingest(payload, search={"keywords": "baker"})
    assert empty["jobs"] == []


def test_indeed_flag_off_returns_nothing():
    payload = json.loads((FIXTURES / "indeed.json").read_text())
    out = indeed_ingest(payload)
    assert out["jobs"] == []
    assert out["reason"] == "flag_off"


def test_indeed_job_sync_xml_and_json_shapes(monkeypatch):
    from app.integrations.indeed_spec import API_CONTRACT, parse_job_sync_xml, spec_bundle
    from app.job_sources.constants import SOURCE_TYPES

    _enable(monkeypatch, indeed=True)
    xml = (FIXTURES / "indeed_job_sync.xml").read_text()
    parsed = parse_job_sync_xml(xml)
    assert {row["referencenumber"] for row in parsed} == {"ind-sync-1", "ind-sync-2"}
    assert all("email" not in row for row in parsed)
    out = indeed_ingest(xml)
    assert out["reason"] == "ok"
    assert out["metrics"]["ingested"] == 2
    titles = {job["title"] for job in out["jobs"]}
    assert titles == {"Staff Platform Engineer", "Senior Backend Engineer"}
    acme = next(job for job in out["jobs"] if job["company"] == "Acme")
    assert acme["location"] == "Austin, TX, US"
    assert acme["postingUrl"].endswith("/ind-sync-1")
    assert acme["sourcePostingId"] == "ind-sync-1"
    assert "should-not-be-ingested" not in str(out)
    assert indeed_ingest(xml.encode("utf-8"))["metrics"]["ingested"] == 2
    json_feed = {
        "sourcedJobPostings": [
            {
                "sourcedPostingId": "js-1",
                "title": "Platform Engineer",
                "companyName": "Initech",
                "url": "https://fixtures.ajas.local/indeed/js-1",
                "location": {"city": "Remote", "country": "US"},
                "description": "python azure",
            }
        ]
    }
    synced = indeed_ingest(json_feed)
    assert synced["jobs"][0]["company"] == "Initech"
    bundle = spec_bundle()
    assert bundle["api"]["publicSearchApi"] is False
    assert API_CONTRACT["publisherApi"] == "retired-2023"
    assert SOURCE_TYPES == frozenset({"greenhouse", "lever"})


def test_glassdoor_partner_envelope_and_pages(monkeypatch):
    from app.integrations.glassdoor_spec import API_CONTRACT, RATE_PLAN, spec_bundle

    _enable(monkeypatch, glassdoor=True)
    payload = json.loads((FIXTURES / "glassdoor_partner.json").read_text())
    out = glassdoor_ingest(payload)
    assert out["reason"] == "ok"
    assert out["metrics"]["ingested"] == 2
    acme = next(job for job in out["jobs"] if job["company"] == "Acme")
    assert acme["title"] == "Staff Platform Engineer"
    assert acme["location"] == "Remote"
    assert acme["postingUrl"].endswith("/gd-partner-1")
    assert acme["sourcePostingId"] == "88001"
    pages = json.loads((FIXTURES / "glassdoor.json").read_text())
    paged = glassdoor_ingest(pages)
    assert paged["metrics"]["ingested"] == 2
    assert paged["metrics"]["pages"] == 2
    _enable(monkeypatch)
    assert glassdoor_ingest(pages)["reason"] == "flag_off"
    _enable(monkeypatch, glassdoor=True)
    expired = glassdoor_ingest(
        {
            "jobs": [
                {
                    "id": "gd-x",
                    "title": "Closed Role",
                    "company": "Acme",
                    "apply_url": "https://fixtures.ajas.local/glassdoor/x",
                    "expired": True,
                }
            ]
        }
    )
    assert expired["jobs"] == []
    assert expired["metrics"]["expiredSkipped"] == 1
    bundle = spec_bundle()
    assert bundle["api"]["publicSearchApi"] is False
    assert API_CONTRACT["partnerApi"] == "closed-to-new-applicants"
    assert RATE_PLAN["ingest"]["capPerWindow"] == 20


def test_linkedin_search_inputs_and_listing_fetcher(monkeypatch):
    spec = parse_search(
        {
            "keywords": "backend",
            "locations": ["Austin", "Remote"],
            "experience": "senior",
            "workplace": "remote",
            "limit": 5,
            "cadenceSeconds": 900,
        }
    )
    assert spec.keywords == "backend"
    assert spec.locations == ("Austin", "Remote")
    assert spec.experience == "senior"
    assert spec.workplace == "remote"
    assert spec.limit == 5
    assert spec.cadence_seconds == 900
    _enable(monkeypatch, linkedin=True)
    payload = {
        "pages": [
            {
                "jobs": [
                    {
                        "id": "li-a",
                        "title": "Senior Backend Engineer",
                        "company": "Globex",
                        "location": "Austin, TX",
                        "description": "python apis. Remote ok.",
                        "url": "https://fixtures.ajas.local/linkedin/li-a",
                    }
                ]
            },
            {
                "jobs": [
                    {
                        "id": "li-b",
                        "title": "Senior Backend Engineer",
                        "company": "Globex",
                        "location": "Austin, TX",
                        "description": "python apis. Remote ok. Kafka.",
                        "url": "https://fixtures.ajas.local/linkedin/li-b",
                    }
                ]
            },
        ]
    }
    out = linkedin_ingest(payload, search={"keywords": "backend", "limit": 10})
    assert out["metrics"]["pages"] == 2
    assert out["metrics"]["ingested"] == 2
    assert {job["sourcePostingId"] for job in out["jobs"]} == {"li-a", "li-b"}


def test_linkedin_normalize_map_dedupe_apply_method(monkeypatch):
    _enable(monkeypatch, linkedin=True)
    payload = json.loads((FIXTURES / "linkedin.json").read_text())
    out = linkedin_ingest(payload)
    job = out["jobs"][0]
    assert job["title"]
    assert job["company"]
    assert job["location"]
    assert job["description"]
    assert job["postingUrl"]
    assert job["sourceMetadata"]["source"] == "linkedin"
    assert job["applyMethod"] == "easy_apply"
    external = detect_apply_method(
        {
            "source": "linkedin",
            "apply_url": "https://boards.greenhouse.io/acme/jobs/1",
            "external_apply_url": "https://boards.greenhouse.io/acme/jobs/1",
        }
    )
    assert external["applyMethod"] == "external"
    store = {job["id"]: job}
    seen = {f"{job['contentHash']}|{job['postingUrl']}": job}
    again = linkedin_ingest(payload, store=store, seen=seen)
    assert again["metrics"]["skipped"] == 1
    assert again["jobs"][0]["id"] == job["id"]


def test_linkedin_scheduler_metrics_and_alerts(monkeypatch):
    _enable(monkeypatch, linkedin=True)
    assert due("linkedin") is True
    tick(payloads={"linkedin": json.loads((FIXTURES / "linkedin.json").read_text())})
    assert due("linkedin", cadence_seconds=3600) is False
    failed = {"reason": "robots_or_consent", "metrics": {"failed": 1, "ingested": 0, "updated": 0, "skipped": 0}}
    record_run("indeed", failed, failed=True)
    record_run("indeed", failed, failed=True)
    third = record_run("indeed", failed, failed=True)
    assert third["consecutiveFailures"] == 3
    assert third["alerts"] >= 1


def test_easy_apply_mapping_attachments_qa_receipts_throttle_captcha(monkeypatch):
    from app.integrations import easy_apply as ea

    _enable(monkeypatch, linkedin=True, easy=True)
    job = {
        "id": "job-1",
        "title": "Staff Engineer",
        "company": "Globex",
        "postingUrl": "https://fixtures.ajas.local/linkedin/job-1",
        "applyMethod": "easy_apply",
    }
    profile = {"full_name": "Alex Jobseeker", "email": "alex@ajas.dev", "phone": "555-0100", "linkedin_url": "https://linkedin.com/in/alex"}
    ok = ea.submit(
        job=job,
        profile=profile,
        questions=[{"key": "work_authorization"}, {"key": "years_experience"}, {"prompt": "salary_expectation"}],
        attachments=[{"kind": "resume", "name": "resume.pdf", "contentType": "application/pdf", "data": b"%PDF-1.4 cv"}],
    )
    assert ok["status"] == "submitted"
    receipt = ok["receipt"]
    assert receipt["confirmation"].startswith("EA-")
    assert receipt["fieldsSent"]["name"] == "Alex Jobseeker"
    assert receipt["fieldsSent"]["email"] == "alex@ajas.dev"
    assert "resume.pdf" in receipt["attachments"]
    assert receipt["answers"]["work_authorization"]
    assert receipt["jobId"] == "job-1"

    limited = ea.submit(job=job, profile=profile, rate_cap=1)
    assert limited["status"] == "rate_limited"

    reset_limiter()
    blocked = ea.submit(job=job, profile=profile, page="<div class='g-recaptcha'></div>")
    assert blocked["status"] == "needs_manual"
    assert blocked["bypass"] is False
    assert blocked["hitl"] is True
    assert any(item["event"] == "captcha" for item in ea.audit_log())
    assert len(ea.receipts()) >= 3

    retry = retry_with_backoff([429, 503, 200], jitter=0.0)
    assert retry["retried"] is True
    assert retry["attempts"][-1]["class"] == "ok"
    assert classify_error(403)["class"] == "permanent"


def test_linkedin_e2e_ingest_review_easy_apply(monkeypatch):
    _enable(monkeypatch, linkedin=True, easy=True)
    payload = json.loads((FIXTURES / "linkedin.json").read_text())
    result = run_linkedin_e2e(
        payload,
        resume_text=RESUME_TEXT,
        profile={"full_name": "Alex Jobseeker", "email": "alex@ajas.dev"},
        decision="approve",
    )
    assert result["jobs"]
    assert result["matches"]
    assert result["reviews"][0]["decision"] == "approve"
    assert result["applies"]
    assert result["applies"][0]["status"] == "submitted"
    assert result["applies"][0]["receipt"]["confirmation"]
    assert result["ok"] is True


def test_greenhouse_harvest_status_mapping_pagination_retries(monkeypatch):
    _enable(monkeypatch, harvest=True)
    pages = [
        {
            "applications": [
                {
                    "id": "app-1",
                    "status": "active",
                    "email": "alex@ajas.dev",
                    "job": {"id": "j1", "name": "Staff"},
                }
            ]
        },
        {
            "applications": [
                {
                    "id": "app-2",
                    "status": "hired",
                    "candidate": {"email": "maya@ajas.dev"},
                    "jobs": [{"id": "j2", "name": "Principal"}],
                }
            ]
        },
    ]
    first = list_applications(api_key="key", pages=pages, page=1)
    assert first["items"][0]["status"] == "submitted"
    assert first["nextPage"] == 2
    second = list_applications(api_key="key", pages=pages, page=2)
    assert second["items"][0]["status"] == "succeeded"
    assert second["nextPage"] is None
    filtered = list_applications(api_key="key", pages=pages, page=1, email="alex@ajas.dev")
    assert len(filtered["items"]) == 1
    assert map_application({"status": "rejected", "id": "x"})["status"] == "failed"
    _enable(monkeypatch)
    disabled = list_applications(api_key="key", pages=pages)
    assert disabled["reason"] == "flag_off"

    class FakeHarvest:
        def __init__(self):
            self.calls = 0

        def request(self, method, url, *, headers):
            self.calls += 1
            return 200, {"applications": [{"id": "live-1", "status": "in_process", "email": "a@b.c"}]}, {"Link": '<https://harvest.greenhouse.io/v1/applications?page=2>; rel="next"'}

    _enable(monkeypatch, harvest=True)
    live = list_applications(api_key="secret", http=FakeHarvest())
    assert live["items"][0]["id"] == "live-1"
    assert live["nextPage"] == 2
    retried = retry_with_backoff([429, 200])
    assert retried["final"]["class"] == "ok"


def test_gmail_sync_parse_and_send(monkeypatch):
    _enable(monkeypatch, gmail=True)
    client = LocalGmailClient()
    synced = sync_inbox(
        "acct-1",
        client=client,
        fixtures=[
            {
                "id": "m1",
                "threadId": "t1",
                "subject": "Interview availability",
                "from": "maya@acme.test",
                "to": ["alex@ajas.dev"],
                "body": "Could we schedule a phone screen this week?",
                "labels": ["INBOX"],
            }
        ],
    )
    assert synced["enabled"] is True
    assert synced["threads"][0]["intent"] == "interview"
    sent = send_mail("acct-1", to_addresses=["maya@acme.test"], subject="Interview availability", body_text="Tue 10am works.", thread_id="t1", client=client)
    assert sent["id"]
    assert sent["threadId"] == "t1"
    _enable(monkeypatch)
    assert sync_inbox("acct-1")["reason"] == "flag_off"


def test_graph_delta_follows_next_link_then_delta_link():
    class PagingHttp:
        def __init__(self):
            self.calls: list[str] = []

        def request(self, method, url, *, headers, body=None):
            self.calls.append(url)
            if "delta" in url and "page=2" not in url and "deltatoken" not in url:
                return 200, {
                    "value": [{"id": "g1", "subject": "One", "from": {"emailAddress": {"address": "a@b.c"}}}],
                    "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages/delta?page=2",
                }
            return 200, {
                "value": [{"id": "g2", "subject": "Two", "from": {"emailAddress": {"address": "c@d.e"}}}],
                "@odata.deltaLink": "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages/delta?$deltatoken=done",
            }

    http = PagingHttp()
    client = HttpGraphClient(token_provider=lambda: "tok", http=http)
    messages, token = client.delta("acct-1", None)
    assert [item.id for item in messages] == ["g1", "g2"]
    assert "deltatoken=done" in token
    assert len(http.calls) == 2


def test_google_drive_import_and_permissions(monkeypatch):
    _enable(monkeypatch, drive=True)
    drive = LocalDriveClient()
    owned = seed_pdf(owner="alex@ajas.dev", data=_pdf())
    other = seed_pdf(name="other.pdf", owner="maya@acme.test", data=_pdf())
    drive.put(owned)
    drive.put(other)
    resume = ResumeService(store=InMemoryResumeStore(), blobs=InMemoryBlobStore(), queue=InMemoryParseQueue(), parser=HeuristicResumeParser())
    from app.integrations.drive import import_resume, list_library

    listed = list_library(drive, user_email="alex@ajas.dev")
    assert {item["id"] for item in listed} == {owned.id}
    imported = import_resume(user_id=USER, user_email="alex@ajas.dev", file_id=owned.id, client=drive, resume_service=resume)
    assert imported["reason"] == "ok"
    assert imported["resumeId"]
    forbidden = import_resume(user_id=USER, user_email="alex@ajas.dev", file_id=other.id, client=drive, resume_service=resume)
    assert forbidden["reason"] == "forbidden"
    missing = import_resume(user_id=USER, user_email="alex@ajas.dev", file_id="nope", client=drive, resume_service=resume)
    assert missing["reason"] == "not_found"
    _enable(monkeypatch)
    off = import_resume(user_id=USER, user_email="alex@ajas.dev", file_id=owned.id, client=drive, resume_service=resume)
    assert off["reason"] == "flag_off"


def test_slack_formatter_and_webhook(monkeypatch):
    _enable(monkeypatch, slack=True)
    http = MemorySlackHttp()
    payload = format_event(kind="match", title="New match", body="Staff at Acme 88")
    assert payload["channel"] == "#ajas-matches"
    posted = post_webhook("https://hooks.slack.test/abc", payload, http=http)
    assert posted["ok"] is True
    assert http.calls[0][1]["text"].startswith("New match")
    event = notify_event(kind="submitted", title="Applied", body="Globex Easy Apply", webhook_url="https://hooks.slack.test/abc", http=http)
    assert event["payload"]["channel"] == "#ajas-apply"
    recruiter = format_event(kind="recruiter_reply", title="Reply", body="phone screen")
    assert recruiter["channel"] == "#ajas-mail"
    _enable(monkeypatch)
    assert notify_event(kind="match", title="x", body="y")["reason"] == "flag_off"


def test_http_routes_flag_gated(monkeypatch):
    _enable(monkeypatch, indeed=True, linkedin=True, glassdoor=True, easy=True, harvest=True, gmail=True, drive=True, slack=True)
    reset_service()
    status = json.loads(routes.integrations_status(_req("GET", "http://localhost/api/v1/integrations/status")).get_body())
    assert status["flags"]["indeed_adapter"] is True
    assert status["flags"]["glassdoor_adapter"] is True
    payload = json.loads((FIXTURES / "indeed.json").read_text())
    ingest = routes.integrations_ingest(
        _req("POST", "http://localhost/api/v1/integrations/ingest/indeed", body={"payload": payload}, route_params={"source": "indeed"})
    )
    assert ingest.status_code in {200, 202}
    body = json.loads(ingest.get_body())
    assert body["jobs"]
    gd = json.loads(
        routes.integrations_ingest(
            _req(
                "POST",
                "http://localhost/api/v1/integrations/ingest/glassdoor",
                body={"payload": json.loads((FIXTURES / "glassdoor_partner.json").read_text())},
                route_params={"source": "glassdoor"},
            )
        ).get_body()
    )
    assert gd["jobs"]
    xml_ingest = json.loads(
        routes.integrations_ingest(
            _req(
                "POST",
                "http://localhost/api/v1/integrations/ingest/indeed",
                body=(FIXTURES / "indeed_job_sync.xml").read_bytes(),
                route_params={"source": "indeed"},
            )
        ).get_body()
    )
    assert xml_ingest["reason"] == "ok"
    assert xml_ingest["metrics"]["ingested"] == 2
    indeed_spec = json.loads(routes.integrations_indeed_spec(_req("GET", "http://localhost/api/v1/integrations/indeed/spec")).get_body())
    assert indeed_spec["api"]["publicSearchApi"] is False
    gd_spec = json.loads(routes.integrations_glassdoor_spec(_req("GET", "http://localhost/api/v1/integrations/glassdoor/spec")).get_body())
    assert gd_spec["flag"] == "glassdoor_adapter"
    search = json.loads(routes.integrations_search_inputs(_req("GET", "http://localhost/api/v1/integrations/linkedin/search", params={"keywords": "python"})).get_body())
    assert search["search"]["keywords"] == "python"
    apply_resp = routes.integrations_easy_apply(
        _req(
            "POST",
            "http://localhost/api/v1/integrations/linkedin/easy-apply",
            body={
                "job": {"id": "x", "title": "Staff", "company": "Acme", "postingUrl": "https://fixtures.ajas.local/x"},
                "profile": {"full_name": "Alex Jobseeker", "email": "alex@ajas.dev"},
                "attachments": [
                    {"kind": "resume", "name": "resume.pdf", "contentType": "application/pdf", "data": "%PDF-1.4 cv"}
                ],
            },
        )
    )
    assert json.loads(apply_resp.get_body())["status"] in {"submitted", "rate_limited"}
    harvest = json.loads(
        routes.integrations_harvest(
            _req("POST", "http://localhost/api/v1/integrations/greenhouse/applications", body={"pages": [{"applications": [{"id": "1", "status": "active", "email": "a@b.c"}]}]})
        ).get_body()
    )
    assert harvest["items"][0]["id"] == "1"
    gmail = json.loads(
        routes.integrations_gmail_sync(
            _req("POST", "http://localhost/api/v1/integrations/gmail/sync", body={"messages": [{"id": "m", "subject": "Following up", "from": "r@x.com", "body": "checking in", "threadId": "t"}]})
        ).get_body()
    )
    assert gmail["threads"][0]["intent"] == "follow_up"
    slack = json.loads(
        routes.integrations_slack(_req("POST", "http://localhost/api/v1/integrations/slack/notify", body={"kind": "match", "title": "Hit", "body": "88"})).get_body()
    )
    assert slack["payload"]["channel"] == "#ajas-matches"


def test_unauthenticated_status_401():
    req = func.HttpRequest(method="GET", url="http://localhost/api/v1/integrations/status", headers={}, params={}, body=b"")
    resp = routes.integrations_status(req)
    assert resp.status_code == 401


def test_throttle_helper():
    reset_limiter()
    assert throttle("indeed", cap=1)["allowed"] is True
    assert throttle("indeed", cap=1)["allowed"] is False


def test_function_app_registers_integration_routes(function_names):
    assert "integrations_refresh" in function_names
    assert "integrations_status" in function_names
    assert "integrations_ingest" in function_names
    assert "cosmos_auto_bootstrap" in function_names
    from app.job_sources.constants import SOURCE_TYPES

    assert SOURCE_TYPES == frozenset({"greenhouse", "lever"})

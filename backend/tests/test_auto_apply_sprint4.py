"""Sprint 4 Auto-Apply gaps: cover letters, manual zip, vendor submit adapters."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from app.config import get_settings
from app.auto_apply.blobs import InMemoryBlobStore
from app.auto_apply.cover import canned_cover_letter, generate_cover_letter
from app.auto_apply.keys import utc_now
from app.auto_apply.memory import InMemoryAutoApplyStore
from app.auto_apply.models import AutoApplyAttempt
from app.auto_apply.package import build_manual_package_zip
from app.auto_apply.queues import InMemoryJobQueue
from app.auto_apply.runtime import set_service
from app.auto_apply.service import AutoApplyService
from app.auto_apply.submitters import greenhouse_endpoint, lever_endpoint, map_vendor_fields, submit_to_vendor
from app.features import auto_apply as routes
import azure.functions as func

USER = "user-1"


def _req(
    method: str,
    url: str,
    *,
    user: str | None = USER,
    json_body=None,
    params: dict | None = None,
    route: dict | None = None,
    headers: dict | None = None,
    scopes: str | None = None,
) -> func.HttpRequest:
    hdrs = dict(headers or {})
    body = b""
    if user:
        hdrs["Authorization"] = f"Bearer {user}"
    if scopes is not None:
        hdrs["X-Scopes"] = scopes
    if json_body is not None:
        hdrs["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode()
    return func.HttpRequest(
        method=method,
        url=url,
        headers=hdrs,
        params=params or {},
        route_params=route or {},
        body=body,
    )


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    return json.loads(raw) if raw else None


def _create_body(**overrides):
    payload = {
        "job_source": "greenhouse",
        "job_posting_id": "job-staff",
        "posting_url": "https://boards.greenhouse.io/acme/jobs/staff",
        "resume_id": "resume-active",
        "cover_letter_mode": "none",
        "consent_approved": True,
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def store():
    return InMemoryAutoApplyStore()


@pytest.fixture
def blobs():
    return InMemoryBlobStore()


@pytest.fixture
def svc(monkeypatch, store, blobs):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = AutoApplyService(store=store, queue=InMemoryJobQueue(), blobs=blobs)
    set_service(service)
    yield service
    set_service(None)
    get_settings.cache_clear()


def test_canned_cover_letter_is_tailored():
    attempt = AutoApplyAttempt(
        user_id=USER,
        vendor="greenhouse",
        mode="api",
        status="queued",
        job_id="staff-engineer",
        posting_url="https://boards.greenhouse.io/acme/jobs/99",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    text = canned_cover_letter(attempt, {"full_name": "Alex Jobseeker", "email": "alex@example.com"})
    assert "Alex Jobseeker" in text
    assert "staff-engineer" in text


def test_generate_cover_falls_back_when_openai_unconfigured(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    attempt = AutoApplyAttempt(
        user_id=USER,
        vendor="lever",
        mode="api",
        status="queued",
        job_id="job-1",
        posting_url="https://jobs.lever.co/acme/abc",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    text = generate_cover_letter(attempt, {"full_name": "Alex Jobseeker"})
    assert "Alex Jobseeker" in text
    get_settings.cache_clear()


def test_create_generate_cover_persists_letter(svc):
    resp = routes.auto_apply_create(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/requests",
            json_body=_create_body(cover_letter_mode="generate"),
        )
    )
    assert resp.status_code == 201
    request_id = _body(resp)["request_id"]
    detail = _body(
        routes.auto_apply_get(
            _req(
                "GET",
                f"http://localhost/api/v1/auto-apply/requests/{request_id}",
                route={"request_id": request_id},
            )
        )
    )
    assert detail["cover_letter_source"] == "ai"
    assert detail["cover_letter_text"]
    assert "Alex Jobseeker" in detail["cover_letter_text"]
    assert detail["artifacts"]["cover_letter_blob_sas"]
    stored = svc.blobs.get(f"cover_letters/{USER}/{request_id}.txt")
    assert stored and b"Alex Jobseeker" in stored


def test_manual_package_writes_zip_with_deep_link(svc):
    resp = routes.auto_apply_create(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/requests",
            json_body=_create_body(
                job_source="manual",
                job_posting_id="job-manual",
                posting_url="https://jobs.example.com/apply",
                cover_letter_mode="generate",
            ),
        )
    )
    assert resp.status_code == 201
    request_id = _body(resp)["request_id"]
    path = f"packages/{USER}/{request_id}.zip"
    raw = svc.blobs.get(path)
    assert raw
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "apply-link.txt" in names
        assert "cover-letter.txt" in names
        assert "fields.json" in names
        assert "https://jobs.example.com/apply" in zf.read("apply-link.txt").decode()


def test_greenhouse_and_lever_endpoints_and_mapping(store):
    store.seed_default_mappings()
    gh = greenhouse_endpoint("https://boards.greenhouse.io/acme/jobs/12345", "job-staff")
    assert gh == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/12345"
    lv = lever_endpoint("https://jobs.lever.co/openai/role-uuid", "job-lever")
    assert lv == "https://api.lever.co/v0/postings/openai/role-uuid"
    fields = map_vendor_fields(
        "greenhouse",
        profile={"full_name": "Alex Jobseeker", "email": "alex@example.com", "phone": "+15555550100"},
        answers={},
        autofill=[],
        mappings=store.list_vendor_mappings("greenhouse"),
    )
    assert fields["first_name"] == "Alex"
    assert fields["last_name"] == "Jobseeker"
    assert fields["email"] == "alex@example.com"


def test_live_submit_uses_poster_and_records_payload(monkeypatch, store, blobs):
    from app.config import get_settings
    from app.auto_apply.queues import InMemoryJobQueue
    from app.auto_apply.runtime import set_service
    from app.auto_apply.service import AutoApplyService

    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("AUTO_APPLY_LIVE_SUBMIT", "true")
    monkeypatch.setenv("GREENHOUSE_SUBMIT_API_KEY", "gh-secret")
    get_settings.cache_clear()

    class FakePoster:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict, dict]] = []

        def post(self, url, payload, headers):
            self.calls.append((url, payload, headers))
            return 201, {"id": "gh-app-99", "request_id": "req-1"}

    poster = FakePoster()
    service = AutoApplyService(store=store, queue=InMemoryJobQueue(), blobs=blobs, poster=poster)
    set_service(service)
    try:
        resp = routes.auto_apply_create(
            _req("POST", "http://localhost/api/v1/auto-apply/requests", json_body=_create_body())
        )
        assert resp.status_code == 201
        assert _body(resp)["state"] == "submitted"
        assert poster.calls
        url, payload, headers = poster.calls[0]
        assert "boards-api.greenhouse.io" in url
        assert headers.get("Authorization") == "Bearer gh-secret"
        assert payload["email"] == "alex@example.com"
        request_id = _body(resp)["request_id"]
        stored = blobs.get(f"provider_payloads/{USER}/{request_id}.json")
        assert stored
        assert json.loads(stored)["status"] == "succeeded"
        detail = _body(
            routes.auto_apply_get(
                _req(
                    "GET",
                    f"http://localhost/api/v1/auto-apply/requests/{request_id}",
                    route={"request_id": request_id},
                )
            )
        )
        assert detail["source"]["external_application_id"] == "gh-app-99"
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_live_lever_submit_appends_key(monkeypatch, store, blobs):
    from app.config import get_settings
    from app.auto_apply.queues import InMemoryJobQueue
    from app.auto_apply.runtime import set_service
    from app.auto_apply.service import AutoApplyService

    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("AUTO_APPLY_LIVE_SUBMIT", "true")
    monkeypatch.setenv("LEVER_SUBMIT_API_KEY", "lv-secret")
    get_settings.cache_clear()

    class FakePoster:
        def post(self, url, payload, headers):
            assert "key=lv-secret" in url
            assert payload["name"] == "Alex Jobseeker"
            return 200, {"application_id": "lever-1"}

    service = AutoApplyService(store=store, queue=InMemoryJobQueue(), blobs=blobs, poster=FakePoster())
    set_service(service)
    try:
        resp = routes.auto_apply_create(
            _req(
                "POST",
                "http://localhost/api/v1/auto-apply/requests",
                json_body=_create_body(
                    job_source="lever",
                    job_posting_id="job-lever",
                    posting_url="https://jobs.lever.co/acme/abcd",
                ),
            )
        )
        assert resp.status_code == 201
        assert _body(resp)["state"] == "submitted"
    finally:
        set_service(None)
        get_settings.cache_clear()


def test_demo_submit_still_succeeds_without_live_flag():
    attempt = AutoApplyAttempt(
        id="aaaaaaaa",
        user_id=USER,
        vendor="greenhouse",
        mode="api",
        status="submitting",
        job_id="job-staff",
        posting_url="https://boards.greenhouse.io/acme/jobs/staff",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    outcome = submit_to_vendor(attempt, {"email": "a@b.c"}, live=False)
    assert outcome.status == "succeeded"
    assert outcome.vendor_application_id.startswith("greenhouse-")


def test_package_zip_helper_includes_readme():
    raw = build_manual_package_zip(
        deep_link="https://example.com/job",
        resume_id="resume-1",
        cover_text="Hello",
        fields={"email": "a@b.c"},
    )
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert zf.read("cover-letter.txt").decode().strip() == "Hello"
        assert "AJAS" in zf.read("README.txt").decode()

"""Auto-Apply Backend PRD — HTTP API, auth, queues."""

from __future__ import annotations

import json

import azure.functions as func
import pytest

from app.config import get_settings
from app.features import auto_apply as routes
from app.auto_apply.blobs import InMemoryBlobStore
from app.auto_apply.memory import InMemoryAutoApplyStore
from app.auto_apply.queues import InMemoryJobQueue
from app.auto_apply.runtime import set_service
from app.auto_apply.service import AutoApplyService

USER = "user-1"


class SilentQueue:
    """Queue that records messages without inline processing."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    def enqueue(self, queue_name: str, message: dict) -> None:
        self.messages.append((queue_name, dict(message)))


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


@pytest.fixture
def queued_svc(monkeypatch, store, blobs):
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    service = AutoApplyService(store=store, queue=SilentQueue(), blobs=blobs)
    set_service(service)
    yield service
    set_service(None)
    get_settings.cache_clear()


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


def test_function_app_registers_auto_apply_routes(function_names):
    assert "auto_apply_create" in function_names
    assert "auto_apply_list" in function_names
    assert "auto_apply_get" in function_names
    assert "auto_apply_cancel" in function_names
    assert "auto_apply_webhook" in function_names
    assert "auto_apply_process_queued" in function_names
    assert "health" in function_names


def test_unauthenticated_is_401(svc):
    resp = routes.auto_apply_list(_req("GET", "http://localhost/api/v1/auto-apply/requests", user=None))
    assert resp.status_code == 401
    assert _body(resp)["error"]["code"] == "UNAUTHENTICATED"


def test_missing_write_scope_is_403(svc):
    resp = routes.auto_apply_create(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/requests",
            json_body=_create_body(),
            scopes="read:auto-apply",
        )
    )
    assert resp.status_code == 403
    assert _body(resp)["error"]["code"] == "FORBIDDEN"


def test_create_greenhouse_submits(svc):
    resp = routes.auto_apply_create(
        _req("POST", "http://localhost/api/v1/auto-apply/requests", json_body=_create_body())
    )
    assert resp.status_code == 201
    created = _body(resp)
    assert created["state"] == "submitted"
    request_id = created["request_id"]

    detail = routes.auto_apply_get(
        _req(
            "GET",
            f"http://localhost/api/v1/auto-apply/requests/{request_id}",
            route={"request_id": request_id},
        )
    )
    body = _body(detail)
    assert detail.status_code == 200
    assert body["state"] == "submitted"
    assert body["source"]["type"] == "greenhouse"
    assert body["source"]["external_application_id"]
    assert body["artifacts"]["resume_blob_sas"]
    events = [row["event"] for row in body["state_history"]]
    assert "queued" in events
    assert "submission_succeeded" in events


def test_manual_and_captcha_urls_package(svc):
    manual = routes.auto_apply_create(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/requests",
            json_body=_create_body(
                job_source="manual",
                job_posting_id="job-manual",
                posting_url="https://jobs.example.com/apply",
            ),
        )
    )
    assert manual.status_code == 201
    assert _body(manual)["state"] == "packaged"

    captcha = routes.auto_apply_create(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/requests",
            json_body=_create_body(
                job_source="greenhouse",
                job_posting_id="job-captcha",
                posting_url="https://boards.greenhouse.io/acme/jobs/captcha-wall",
            ),
        )
    )
    assert captcha.status_code == 201
    request_id = _body(captcha)["request_id"]
    detail = _body(
        routes.auto_apply_get(
            _req(
                "GET",
                f"http://localhost/api/v1/auto-apply/requests/{request_id}",
                route={"request_id": request_id},
            )
        )
    )
    assert detail["state"] == "packaged"
    assert detail["artifacts"]["package_blob_sas"]
    assert "captcha" in (detail["artifacts"]["deep_link_url"] or "")


def test_rate_limited_posting_url(svc):
    resp = routes.auto_apply_create(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/requests",
            json_body=_create_body(job_posting_id="job-429", posting_url="https://boards.greenhouse.io/acme/jobs/429"),
        )
    )
    assert resp.status_code == 201
    assert _body(resp)["state"] == "rate_limited"


def test_validation_and_consent(svc):
    missing = routes.auto_apply_create(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/requests",
            json_body={"job_source": "greenhouse", "consent_approved": True},
        )
    )
    assert missing.status_code == 400
    refused = routes.auto_apply_create(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/requests",
            json_body=_create_body(consent_approved=False),
        )
    )
    assert refused.status_code == 400


def test_duplicate_in_flight_is_409(queued_svc):
    first = routes.auto_apply_create(
        _req("POST", "http://localhost/api/v1/auto-apply/requests", json_body=_create_body())
    )
    assert first.status_code == 201
    assert _body(first)["state"] == "queued"
    second = routes.auto_apply_create(
        _req("POST", "http://localhost/api/v1/auto-apply/requests", json_body=_create_body())
    )
    assert second.status_code == 409
    body = _body(second)
    assert body["error"]["code"] == "CONFLICT"
    assert body["error"]["details"]["request_id"] == _body(first)["request_id"]


def test_cancel_queued_then_conflict_when_already_cancelled(queued_svc):
    created = routes.auto_apply_create(
        _req("POST", "http://localhost/api/v1/auto-apply/requests", json_body=_create_body())
    )
    request_id = _body(created)["request_id"]
    cancelled = routes.auto_apply_cancel(
        _req(
            "POST",
            f"http://localhost/api/v1/auto-apply/requests/{request_id}/cancel",
            route={"request_id": request_id},
        )
    )
    assert cancelled.status_code == 202
    assert _body(cancelled)["state"] == "cancelled"

    again = routes.auto_apply_cancel(
        _req(
            "POST",
            f"http://localhost/api/v1/auto-apply/requests/{request_id}/cancel",
            route={"request_id": request_id},
        )
    )
    assert again.status_code == 409


def test_cannot_cancel_after_submit(svc):
    row = routes.auto_apply_create(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/requests",
            json_body=_create_body(),
        )
    )
    submitted_id = _body(row)["request_id"]
    late = routes.auto_apply_cancel(
        _req(
            "POST",
            f"http://localhost/api/v1/auto-apply/requests/{submitted_id}/cancel",
            route={"request_id": submitted_id},
        )
    )
    assert late.status_code == 409


def test_list_and_unknown_are_scoped(svc):
    created = routes.auto_apply_create(
        _req("POST", "http://localhost/api/v1/auto-apply/requests", json_body=_create_body())
    )
    listed = routes.auto_apply_list(_req("GET", "http://localhost/api/v1/auto-apply/requests"))
    assert listed.status_code == 200
    items = _body(listed)["items"]
    assert any(row["request_id"] == _body(created)["request_id"] for row in items)

    other = routes.auto_apply_list(_req("GET", "http://localhost/api/v1/auto-apply/requests", user="user-2"))
    assert _body(other)["items"] == []

    missing = routes.auto_apply_get(
        _req(
            "GET",
            "http://localhost/api/v1/auto-apply/requests/does-not-exist",
            route={"request_id": "does-not-exist"},
        )
    )
    assert missing.status_code == 404


def test_webhook_ingest(svc):
    created = routes.auto_apply_create(
        _req("POST", "http://localhost/api/v1/auto-apply/requests", json_body=_create_body())
    )
    request_id = _body(created)["request_id"]
    detail = _body(
        routes.auto_apply_get(
            _req(
                "GET",
                f"http://localhost/api/v1/auto-apply/requests/{request_id}",
                route={"request_id": request_id},
            )
        )
    )
    vendor_app = detail["source"]["external_application_id"]
    resp = routes.auto_apply_webhook(
        _req(
            "POST",
            "http://localhost/api/v1/auto-apply/webhooks/greenhouse",
            json_body={"vendor_application_id": vendor_app, "event_type": "vendor_ack"},
            route={"provider": "greenhouse"},
            headers={"X-Webhook-Secret": "dev-webhook-secret"},
            user=None,
        )
    )
    assert resp.status_code == 202
    payload = _body(resp)
    assert payload["vendor_application_id"] == vendor_app
    assert payload["auto_apply_id"] == request_id


def test_queue_worker_processes_payload(store, blobs):
    service = AutoApplyService(store=store, queue=SilentQueue(), blobs=blobs)
    set_service(service)
    _, created = service.create_request(USER, _create_body())
    assert created["state"] == "queued"

    class _Msg:
        dequeue_count = 1

        def get_body(self):
            return json.dumps(
                {"eventType": "AutoApplyQueued", "userId": USER, "requestId": created["request_id"]}
            ).encode()

    routes.auto_apply_process_queued(_Msg())
    detail = service.get_request(USER, created["request_id"])
    assert detail["state"] == "submitted"
    set_service(None)

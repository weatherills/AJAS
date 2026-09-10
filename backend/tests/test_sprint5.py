"""Sprint 5 polish: matching timeout/AB, settings audit/flag, auto-apply, mail, SLO."""

from __future__ import annotations

import json
import time

import azure.functions as func
import pytest

from app.auto_apply.blobs import InMemoryBlobStore
from app.auto_apply.memory import InMemoryAutoApplyStore
from app.auto_apply.queues import InMemoryJobQueue as ApplyQueue
from app.auto_apply.runtime import set_service as set_apply
from app.auto_apply.service import AutoApplyService
from app.auto_apply.validation import retry_backoff_seconds, validate_apply_fields
from app.config import get_settings
from app.features import matching as match_routes
from app.features import settings as settings_routes
from app.mail.bounce import classify_delivery, thread_fingerprint
from app.mail.pii import redact_pii
from app.matching.ab import assign_variant, weights_for
from app.matching.embedder import HashEmbedder
from app.matching.memory import InMemoryMatchingStore
from app.matching.queues import InMemoryJobQueue
from app.matching.runtime import set_service as set_matching
from app.matching.service import MatchingService
from app.settings.memory import InMemorySettingsStore
from app.settings.oauth import REQUIRED_SCOPES
from app.settings.runtime import set_service as set_settings
from app.settings.service import SettingsService
from app.slo import record_latency, snapshot


USER = "user-1"
RESUME = "Staff engineer Python Azure Cosmos Functions Kubernetes Terraform " + ("x" * 40)
JOB = "Title: Platform Engineer\nSkills: python azure cosmos kubernetes\nShip services on Azure Functions."


class SlowEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        time.sleep(0.25)
        return HashEmbedder().embed(texts)


def _req(method: str, url: str, *, user: str | None = USER, json_body=None, route=None) -> func.HttpRequest:
    headers = {}
    body = b""
    if user:
        headers["Authorization"] = f"Bearer {user}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode()
    return func.HttpRequest(method=method, url=url, headers=headers, params={}, route_params=route or {}, body=body)


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    return json.loads(raw) if raw else None


@pytest.fixture
def matching(monkeypatch):
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("MATCH_AB_TEST", raising=False)
    get_settings.cache_clear()
    service = MatchingService(store=InMemoryMatchingStore(), queue=InMemoryJobQueue(), embedder=HashEmbedder())
    set_matching(service)
    yield service
    set_matching(None)
    get_settings.cache_clear()


@pytest.fixture
def settings_svc(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    get_settings.cache_clear()
    service = SettingsService(store=InMemorySettingsStore())
    set_settings(service)
    yield service
    set_settings(None)
    get_settings.cache_clear()


def test_graph_scopes_are_least_privilege():
    assert REQUIRED_SCOPES == ["offline_access", "Mail.Read", "Mail.Send"]


def test_settings_auto_apply_flag_and_audit(settings_svc):
    got = _body(settings_routes.get_settings(_req("GET", "http://localhost/api/v1/settings")))
    assert got["autoApplyEnabled"] is True
    patched = _body(
        settings_routes.patch_settings(
            _req("PATCH", "http://localhost/api/v1/settings", json_body={"autoApplyEnabled": False})
        )
    )
    assert patched["autoApplyEnabled"] is False
    audit = _body(settings_routes.list_settings_audit(_req("GET", "http://localhost/api/v1/settings/audit")))
    assert any("auto_apply_enabled" in item["fieldMask"] for item in audit["items"])


def test_matching_timeout_falls_back_to_keyword_only(monkeypatch, matching):
    monkeypatch.setenv("MATCH_SEMANTIC_TIMEOUT_SEC", "0.05")
    get_settings.cache_clear()
    slow = MatchingService(store=InMemoryMatchingStore(), queue=InMemoryJobQueue(), embedder=SlowEmbedder())
    set_matching(slow)
    resp = match_routes.compute_match(
        _req(
            "POST",
            "http://localhost/api/v1/matches/compute",
            json_body={"resumeText": RESUME, "jobText": JOB, "threshold": 10},
        )
    )
    body = _body(resp)
    assert resp.status_code == 200
    assert body["breakdown"]["fallback"] == "keyword_only"
    assert body["breakdown"]["weights"] == {"keyword": 1.0, "semantic": 0.0}
    assert slow.semantic_fallback_events >= 1
    get_settings.cache_clear()


def test_matching_warmup_and_slo(matching):
    warm = _body(match_routes.warmup_matches(_req("POST", "http://localhost/api/v1/matches/warmup")))
    assert warm["warm"] is True
    variant = _body(match_routes.match_ab_variant(_req("GET", "http://localhost/api/v1/matching/ab-variant")))
    assert variant["variant"] == "control"
    record_latency("POST /v1/matches/compute", 10)
    slo = _body(match_routes.matching_slo(_req("GET", "http://localhost/api/v1/ops/slo")))
    assert slo["slo"]
    assert "alerts" in slo


def test_ab_variant_assignment(monkeypatch):
    monkeypatch.setenv("MATCH_AB_TEST", "true")
    keyword, semantic, name = weights_for("user-1", 0.4, 0.6)
    assert name in {"kw30", "balanced"}
    assert (keyword, semantic) != (0.4, 0.6)
    assert assign_variant("user-1") == assign_variant("user-1")


def test_auto_apply_validation_and_flag(settings_svc, monkeypatch):
    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    get_settings.cache_clear()
    apply = AutoApplyService(store=InMemoryAutoApplyStore(), queue=ApplyQueue(), blobs=InMemoryBlobStore())
    set_apply(apply)
    settings_routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"autoApplyEnabled": False})
    )
    with pytest.raises(Exception) as exc:
        apply.create_request(
            USER,
            {
                "job_source": "greenhouse",
                "job_posting_id": "job-1",
                "consent_approved": True,
            },
        )
    assert "disabled" in str(exc.value).lower()
    settings_routes.patch_settings(
        _req("PATCH", "http://localhost/api/v1/settings", json_body={"autoApplyEnabled": True})
    )
    with pytest.raises(Exception):
        validate_apply_fields({"answers": {"email": "not-an-email", "full_name": "A"}}, {"email": "not-an-email", "full_name": "A"})
    assert retry_backoff_seconds(3) == 8
    set_apply(None)


def test_mail_bounce_and_pii():
    assert classify_delivery("mailer-daemon@outlook.com", "Undeliverable: hello") == "bounced"
    assert classify_delivery("maya@acme.test", "Deferred: mailbox busy") == "deferred"
    left = thread_fingerprint("Re: Staff role", ["Maya@Acme.test", "me@ajas.dev"])
    right = thread_fingerprint("Staff role", ["me@ajas.dev", "maya@acme.test"])
    assert left == right
    assert "[redacted-email]" in redact_pii("Write jane@contoso.com please")


def test_retry_backoff_caps():
    assert retry_backoff_seconds(1) == 2
    assert retry_backoff_seconds(10) == 60

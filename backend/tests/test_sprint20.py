from __future__ import annotations

import pytest

from app.sprint20 import COMPLETED, VERSION
from app.sprint20.kanban import HANDLERS, extra_board_flag, reset, run, status, titles


def setup_function() -> None:
    reset()


def test_kanban_has_fifty_titles():
    assert len(titles()) == 50 == COMPLETED
    assert set(titles()) == set(HANDLERS)
    assert VERSION == "sprint20"
    payload = status()
    assert payload["liveFetch"] == ["greenhouse", "lever"]
    assert payload["kanban"] == 50
    assert payload["thresholdDefault"] == 70
    assert payload["weights"] == {"keyword": 0.4, "semantic": 0.6}


@pytest.mark.parametrize("title", list(titles()))
def test_each_sprint20_card(title: str):
    out = run(title)
    assert out["ok"] is True


def test_live_fetch_greenhouse_lever_only():
    fixtures = run("[Sprint 20] Adapter unit tests (fixtures)")
    assert fixtures["liveFetch"] == ["greenhouse", "lever"]
    assert fixtures["extraFlagsOff"] is False
    assert extra_board_flag("indeed_adapter") is True
    assert extra_board_flag("linkedin_adapter") is True
    scheduled = run("[Sprint 20] Scheduler: cron + event triggers")
    assert "indeed" in scheduled["skipped"]


def test_source_toggles_honored_at_schedule():
    from app.sprint20.kanban import scheduler, source_toggles

    source_toggles(greenhouse=False, lever=True)
    row = scheduler(due=["greenhouse", "lever"])
    assert "greenhouse" in row["skipped"]
    assert len(row["queued"]) == 1


def test_rate_limit_three_rps():
    from app.sprint20.kanban import rate_limit

    reset()
    assert rate_limit(source="greenhouse", cost=1, cap=3)["allowed"] is True
    assert rate_limit(source="greenhouse", cost=1, cap=3)["allowed"] is True
    assert rate_limit(source="greenhouse", cost=1, cap=3)["allowed"] is True
    assert rate_limit(source="greenhouse", cost=1, cap=3)["allowed"] is False
    assert rate_limit(source="indeed", cost=1, cap=10)["allowed"] is False


def test_backoff_retryable_on_429_and_5xx():
    from app.sprint20.kanban import backoff

    assert backoff(attempt=2, status=429)["retryable"] is True
    assert backoff(attempt=2, status=503)["retryable"] is True
    assert backoff(attempt=2, status=400)["retryable"] is False


def test_canonical_dedupe_omits_source():
    from app.sprint20.kanban import canonical_util, upsert_job

    a = canonical_util(source="greenhouse")
    b = canonical_util(source="lever")
    assert a["hash"] == b["hash"]
    assert a["sourceOmitted"] is True
    reset()
    first = upsert_job({"title": "Staff", "company": "Acme", "location": "Remote", "apply_url": "https://x/1", "source": "greenhouse"})
    second = upsert_job({"title": "Staff", "company": "Acme", "location": "Remote", "apply_url": "https://x/1", "source": "lever"})
    assert first["created"] is True
    assert second["created"] is False


def test_https_allowlist_and_circuit():
    from app.sprint20.kanban import http_client

    ok = http_client(url="https://boards-api.greenhouse.io/v1/boards/acme/jobs", source="greenhouse")
    assert ok["ssrfBlocked"] is False
    assert ok["circuit"] is True
    blocked = http_client(url="http://169.254.169.254/", source="greenhouse")
    assert blocked["ssrfBlocked"] is True


def test_matching_0_100_threshold_70():
    scored = run("[Sprint 20] Combined score function")
    assert 0 <= scored["total"] <= 100
    assert scored["keywordWeight"] == 0.4
    gate = run("[Sprint 20] Threshold gate in pipeline")
    assert gate["thresholdUsed"] == 70
    assert gate["persist"] == (gate["total"] >= 70)
    batch = run("[Sprint 20] Batch scoring worker")
    assert batch["persistPolicy"] == "gte-threshold"


def test_graph_tokens_sealed_and_email_pii():
    token = run("[Sprint 20] Graph OAuth token cache")
    assert token["sealed"] is True
    assert token["plaintextStored"] is False
    mail = run("[Sprint 20] Email normalizer")
    assert "[redacted-email]" in mail["message"]["log"]
    assert "ada@example.test" not in mail["message"]["log"]


def test_message_upsert_and_thread_link():
    from app.sprint20.kanban import upsert_message

    first = upsert_message(message_id="m-9")
    second = upsert_message(message_id="m-9")
    assert first["created"] is True
    assert second["duplicate"] is True
    linked = run("[Sprint 20] Email-to-entity linking tests")
    assert linked["sameThread"] is True


def test_captcha_never_bypassed_and_submit_redacts():
    from app.sprint20.kanban import orchestrator, submit_client

    blocked = submit_client(
        vendor="greenhouse",
        profile={"full_name": "Ada", "email": "ada@example.test"},
        posting_url="https://boards.greenhouse.io/acme/jobs/1?captcha=1",
    )
    assert blocked["status"] == "needs_manual"
    assert blocked["bypass"] is False
    gh = run("[Sprint 20] Greenhouse submit client")
    assert gh["dryRun"] is True
    assert "[redacted]" in str(gh["payload"].get("email"))
    packaged = orchestrator(posting_url="https://boards.greenhouse.io/acme/jobs/1?recaptcha=1")
    assert packaged["packaged"] is True
    assert packaged["bypass"] is False


def test_apply_fsm_and_review_decision():
    from app.sprint20.kanban import apply_fsm, persist_decision

    assert apply_fsm(status="draft", action="queued")["valid"] is True
    assert apply_fsm(status="succeeded", action="queued")["valid"] is False
    bad = persist_decision(decision="maybe")
    assert bad["ok"] is False
    good = persist_decision(decision="approve", comment="fit")
    assert good["decision"]["decision"] == "approve"
    hist = run("[Sprint 20] Decision history API")
    assert hist["items"]


def test_templates_and_enums():
    enums = run("[Sprint 20] Normalize employment/location enums")
    assert enums["employment"] == "FT"
    assert enums["location"] == "Remote"
    from app.sprint20.kanban import TEMPLATE_KEYS

    assert TEMPLATE_KEYS == ("{firstName}", "{company}", "{role}", "{jobRef}")


def test_dlq_redacts_secrets():
    row = run("[Sprint 20] DLQ for failed fetch jobs")
    assert row["secretsRedacted"] is True
    assert "secret-token" not in str(row["item"])


def test_health_v9_and_status_payload():
    from app.features.health import _status_payload
    from app.sprint20.ops import health_v9

    assert _status_payload()["version"] == "sprint20"
    row = health_v9()
    assert row["version"] == "sprint20"
    assert row["schema"] == "ajas.health.v9"

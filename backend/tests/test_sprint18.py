from __future__ import annotations

import pytest

from app.sprint18 import COMPLETED, VERSION
from app.sprint18.kanban import HANDLERS, extra_board_flag, reset, run, status, titles


def setup_function() -> None:
    reset()


def test_kanban_has_fifty_titles():
    assert len(titles()) == 50 == COMPLETED
    assert set(titles()) == set(HANDLERS)
    assert VERSION == "sprint18"
    payload = status()
    assert payload["liveFetch"] == ["greenhouse", "lever"]
    assert payload["kanban"] == 50
    assert payload["thresholdDefault"] == 70
    assert payload["weights"] == {"keyword": 0.4, "semantic": 0.6}


@pytest.mark.parametrize("title", list(titles()))
def test_each_sprint18_card(title: str):
    out = run(title)
    assert out["ok"] is True


def test_live_fetch_is_greenhouse_and_lever_only():
    smoke = run("[Sprint 18][BE] Job Sources: Adapter smoke tests")
    assert smoke["liveFetch"] == ["greenhouse", "lever"]
    assert smoke["greenhouse"]["title"] == "Staff"
    assert smoke["lever"]["title"] == "Staff"
    planned = run("[Sprint 18][BE] Source Ingestion: Crawl planner")
    assert planned["planned"] == ["greenhouse", "lever"]
    assert "indeed" in planned["skipped"]


def test_extra_boards_stay_off():
    assert extra_board_flag("indeed_adapter") is True
    assert extra_board_flag("linkedin_adapter") is True
    assert extra_board_flag("glassdoor_adapter") is True


def test_https_allowlist_blocks_ssrf():
    from app.sprint18.kanban import http_client

    ok = http_client(url="https://boards-api.greenhouse.io/v1/boards/acme/jobs", source="greenhouse")
    assert ok["ssrfBlocked"] is False
    blocked = http_client(url="http://169.254.169.254/", source="greenhouse")
    assert blocked["ssrfBlocked"] is True
    other = http_client(url="https://evil.example/steal", source="greenhouse")
    assert other["ssrfBlocked"] is True


def test_rate_limit_cap_is_three_rps():
    row = run("[Sprint 18][BE] Source Ingestion: Retry policy config")
    assert row["maxRps"] == 3
    client = run("[Sprint 18][BE] Job Sources: Common HTTP client")
    assert client["rpsCap"] == 3


def test_captcha_never_bypassed():
    from app.sprint18.kanban import apply_executor

    row = apply_executor(
        vendor="greenhouse",
        profile={"full_name": "Ada", "email": "a@b.c"},
        posting_url="https://boards.greenhouse.io/acme/jobs/1?captcha=1",
    )
    assert row["captcha"] is True
    assert row["bypass"] is False
    assert row["status"] == "needs_manual"


def test_submit_redacts_email_and_is_dry_run():
    row = run("[Sprint 18][BE] Auto-Apply: GH submit adapter skeleton")
    assert row["dryRun"] is True
    assert "[redacted]" in str(row["payload"].get("email"))
    assert row["bypass"] is False


def test_idempotency_is_user_job_resume():
    row = run("[Sprint 18][BE] Auto-Apply: Idempotency design")
    assert row["uniqueOn"] == ["user_id", "job_id", "resume_id"]
    assert row["secondReplay"] is True


def test_graph_tokens_are_sealed():
    row = run("[Sprint 18][BE] Email: Token store & rotation")
    assert row["sealed"] is True
    assert row["rotated"] is True
    assert row["plaintextStored"] is False
    assert row["matches"] is True


def test_email_send_requires_owner_and_redacts_pii():
    from app.sprint18.kanban import outbound_send, quarantine_pii

    denied = outbound_send(user_id="eve", mailbox_owner="ada", body="hi {firstName}")
    assert denied["ok"] is False
    allowed = outbound_send(user_id="ada", mailbox_owner="ada", body="Hi {firstName} at {company} for {role} {jobRef}")
    assert allowed["sent"] is True
    assert "Ada" in allowed["message"]["log"] or allowed["message"]["bodyHash"]
    pii = quarantine_pii()
    assert "[redacted-email]" in pii["redacted"]
    assert "[redacted-ssn]" in pii["redacted"]


def test_templates_use_prd_placeholders():
    row = run("[Sprint 18][BE] Email: Outbound send service")
    assert "{firstName}" in row["placeholders"]
    assert "{company}" in row["placeholders"]
    assert "{role}" in row["placeholders"]
    assert "{jobRef}" in row["placeholders"]


def test_webhook_to_reply_e2e():
    row = run("[Sprint 18][BE] Email: E2E webhook-to-reply test")
    assert row["e2e"] is True
    assert row["sent"] is True


def test_dsn_classifies_bounces():
    row = run("[Sprint 18][BE] Email: Delivery/DSN handling")
    assert row["bounced"] is True
    assert row["deliveryStatus"] == "bounced"


def test_matching_score_is_0_100_and_gated():
    from app.sprint18.kanban import batch_scoring, threshold_api

    scored = batch_scoring(resume="python azure kubernetes", jobs=["title: platform\npython azure kubernetes"])
    total = scored["items"][0]["total"]
    assert 0 <= total <= 100
    weak = batch_scoring(resume="gardening", jobs=["title: quantum physics researcher"])
    assert weak["items"][0]["saved"] is False or weak["items"][0]["total"] < 70
    bad = threshold_api(user_id="ada", value=140)
    assert bad["ok"] is False
    good = threshold_api(user_id="ada", value=70)
    assert good["threshold"] == 70


def test_upsert_dedupes_across_greenhouse_and_lever():
    from app.sprint18.kanban import upsert_dal

    reset()
    a = upsert_dal({"title": "Staff", "company": "Acme", "location": "Remote", "apply_url": "https://x/1", "source": "greenhouse"})
    b = upsert_dal({"title": "Staff", "company": "Acme", "location": "Remote", "apply_url": "https://x/1", "source": "lever"})
    assert a["hash"] == b["hash"]
    assert a["created"] is True
    assert b["created"] is False


def test_dlq_redacts_secrets():
    row = run("[Sprint 18][BE] Source Ingestion: Dead-letter queue")
    assert row["secretsRedacted"] is True
    assert "super-secret" not in str(row["item"])


def test_cover_letter_hook_uses_name():
    row = run("[Sprint 18][BE] Auto-Apply: Cover letter generator hookpoint")
    assert "Ada" in row["text"]


def test_health_v7_and_status_payload():
    from app.features.health import _status_payload
    from app.sprint18.ops import health_v7

    assert _status_payload()["version"] == "sprint20"
    row = health_v7()
    assert row["version"] == "sprint18"
    assert row["schema"] == "ajas.health.v7"

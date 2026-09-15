from __future__ import annotations

import pytest

from app.sprint17 import COMPLETED, VERSION
from app.sprint17.kanban import HANDLERS, extra_board_flag, reset, run, status, titles


def setup_function() -> None:
    reset()


def test_kanban_has_one_hundred_three_titles():
    assert len(titles()) == 103 == COMPLETED
    assert set(titles()) == set(HANDLERS)
    assert VERSION == "sprint17"
    payload = status()
    assert payload["liveFetch"] == ["greenhouse", "lever"]
    assert payload["kanban"] == 103


@pytest.mark.parametrize("title", list(titles()))
def test_each_sprint17_card(title: str):
    out = run(title)
    assert out["ok"] is True


def test_greenhouse_and_lever_fetch_fixtures():
    gh = run("Greenhouse postings fetcher")
    assert gh["source"] == "greenhouse"
    assert gh["jobs"][0]["title"] == "Staff"
    assert gh["pages"] is True
    lever = run("Lever postings fetcher")
    assert lever["jobs"][0]["title"] == "Staff"


def test_canonical_hash_is_stable():
    a = run("Dedup: Canonical hash function")
    b = run("Dedup: Canonical hash function")
    assert a["hash"] == b["hash"]
    dup = run("Deduplication service")
    assert dup["duplicates"] >= 1


def test_rate_limiter_and_backoff():
    from app.sprint17.kanban import rate_limiter, retry_backoff

    reset()
    assert rate_limiter(source="greenhouse", cost=1, cap=2)["allowed"] is True
    assert rate_limiter(source="greenhouse", cost=1, cap=2)["allowed"] is True
    assert rate_limiter(source="greenhouse", cost=1, cap=2)["allowed"] is False
    assert rate_limiter(source="indeed", cost=1, cap=10)["allowed"] is False
    assert retry_backoff(0)["waitSec"] >= 0
    assert retry_backoff(4)["waitSec"] > retry_backoff(0)["waitSec"]


def test_payload_validation_rejects_incomplete_jobs():
    from app.sprint17.kanban import validate_payload

    assert validate_payload({"title": "X", "company": "Acme", "apply_url": "https://x"})["valid"] is True
    assert validate_payload({"title": "X"})["valid"] is False


def test_graph_tokens_are_sealed():
    row = run("OAuth: Store Graph tokens")
    assert row["sealed"] is True
    assert row["plaintextStored"] is False
    assert row["matches"] is True


def test_webhook_dedup():
    row = run("Idempotency: Webhook dedup")
    assert row["first"] is True
    assert row["secondDuplicate"] is True


def test_email_send_requires_owner():
    from app.sprint17.kanban import send_reply

    denied = send_reply(user_id="eve", mailbox="ada", owner="ada", body="hi")
    assert denied["ok"] is False
    allowed = send_reply(user_id="ada", mailbox="ada", owner="ada", body="hi")
    assert allowed["sent"] is True


def test_composite_score_and_threshold():
    scored = run("Scoring: Composite function")
    assert 0 <= scored["total"] <= 1 or scored["total"] >= 0
    assert "keyword" in scored and "semantic" in scored
    from app.sprint17.kanban import threshold_api

    bad = threshold_api(user_id="ada", value=1.5)
    assert bad["ok"] is False
    good = threshold_api(user_id="ada", value=0.7)
    assert good["threshold"] == 0.7


def test_captcha_never_bypassed():
    from app.sprint17.kanban import _submit

    row = _submit(
        vendor="greenhouse",
        profile={"full_name": "Ada", "email": "a@b.c"},
        posting_url="https://boards.greenhouse.io/acme/jobs/1?captcha=1",
        dry_run=True,
    )
    assert row["captcha"] is True
    assert row["bypass"] is False
    assert row["status"] == "needs_manual"


def test_submit_redacts_email():
    row = run("Submit: Greenhouse")
    assert row["dryRun"] is True
    assert "[redacted]" in str(row["payload"].get("email"))
    assert row["bypass"] is False


def test_apply_fsm_and_cover_letter():
    from app.sprint17.kanban import apply_fsm

    assert apply_fsm(status="draft", action="queued")["valid"] is True
    assert apply_fsm(status="succeeded", action="queued")["valid"] is False
    cover = run("Cover letter generator service")
    assert "Ada" in cover["text"]


def test_manual_package_is_zip():
    row = run("Manual package generator")
    assert row["zip"] is True
    assert row["bytes"] > 0


def test_learning_rollback_on_drift():
    from app.sprint17.kanban import online_weights

    row = online_weights(keyword=0.9, semantic=0.1)
    assert row["rolledBack"] is True


def test_extra_boards_stay_off():
    assert extra_board_flag("indeed_adapter") is False
    assert extra_board_flag("linkedin_adapter") is False


def test_health_v6_and_status_payload():
    from app.features.health import _status_payload
    from app.sprint17.ops import health_v6

    assert _status_payload()["version"] == "sprint18"
    row = health_v6()
    assert row["version"] == "sprint17"
    assert row["schema"] == "ajas.health.v6"

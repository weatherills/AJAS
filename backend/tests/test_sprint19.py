from __future__ import annotations

import pytest

from app.sprint19 import COMPLETED, VERSION
from app.sprint19.kanban import HANDLERS, extra_board_flag, reset, run, status, titles


def setup_function() -> None:
    reset()


def test_kanban_has_fifty_titles():
    assert len(titles()) == 50 == COMPLETED
    assert set(titles()) == set(HANDLERS)
    assert VERSION == "sprint19"
    payload = status()
    assert payload["liveFetch"] == ["greenhouse", "lever"]
    assert payload["kanban"] == 50
    assert payload["thresholdDefault"] == 70
    assert payload["weights"] == {"keyword": 0.4, "semantic": 0.6}


@pytest.mark.parametrize("title", list(titles()))
def test_each_sprint19_card(title: str):
    out = run(title)
    assert out["ok"] is True


def test_live_fetch_greenhouse_lever_only():
    stubs = run("[Sprint 19][BE] Source Ingestion: Integration tests (GH/Lever stubs)")
    assert stubs["liveFetch"] == ["greenhouse", "lever"]
    assert stubs["greenhouse"] == "Staff"
    sched = run("[Sprint 19][BE] Source Ingestion: Scheduler trigger")
    assert "indeed" in sched["skipped"]
    assert extra_board_flag("indeed_adapter") is False
    assert extra_board_flag("linkedin_adapter") is False


def test_rate_limit_three_rps_and_extra_sources_blocked():
    from app.sprint19.kanban import rate_limit

    reset()
    assert rate_limit(source="greenhouse", cost=1, cap=3)["allowed"] is True
    assert rate_limit(source="greenhouse", cost=1, cap=3)["allowed"] is True
    assert rate_limit(source="greenhouse", cost=1, cap=3)["allowed"] is True
    assert rate_limit(source="greenhouse", cost=1, cap=3)["allowed"] is False
    assert rate_limit(source="indeed", cost=1, cap=10)["allowed"] is False


def test_captcha_never_bypassed_and_pii_redacted():
    row = run("[Sprint 19][BE] Auto-Apply: E2E apply test")
    assert row["captchaStatus"] == "needs_manual"
    assert row["bypass"] is False
    gh = run("[Sprint 19][BE] Auto-Apply: Greenhouse submit adapter")
    assert gh["dryRun"] is True
    assert "[redacted]" in str(gh["payload"].get("email"))
    audit = run("[Sprint 19][BE] Auto-Apply: Audit logging")
    assert audit["piiLeaked"] is False


def test_idempotency_user_job_resume():
    row = run("[Sprint 19][BE] Auto-Apply: Retry & idempotency")
    assert row["uniqueOn"] == ["user_id", "job_id", "resume_id"]
    assert row["secondReplay"] is True


def test_graph_oauth_sealed_and_owner_send():
    oauth = run("[Sprint 19][BE] Email: Graph OAuth handler")
    assert oauth["sealed"] is True
    assert oauth["plaintextStored"] is False
    from app.sprint19.kanban import send_mail

    denied = send_mail(user_id="eve", owner="ada")
    assert denied["ok"] is False
    allowed = send_mail(user_id="ada", owner="ada")
    assert allowed["sent"] is True


def test_templates_and_e2e_sync():
    tmpl = run("[Sprint 19][BE] Email: Template renderer")
    assert set(tmpl["placeholders"]) == {"{firstName}", "{company}", "{role}", "{jobRef}"}
    sync = run("[Sprint 19][BE] Email: E2E sync test")
    assert sync["e2e"] is True
    assert sync["sent"] is True


def test_matching_0_100_threshold_70():
    scored = run("[Sprint 19][BE] Matching: Weighted ensemble")
    assert 0 <= scored["total"] <= 100
    gate = run("[Sprint 19][BE] Matching: Threshold gate")
    assert gate["threshold"] == 70
    batch = run("[Sprint 19][BE] Matching: Batch pipeline")
    assert batch["persistPolicy"] == "gte-threshold"
    assert batch["items"][0]["saved"] == (batch["items"][0]["total"] >= 70)


def test_scorer_and_explanation():
    row = run("[Sprint 19][BE] Matching: Scorer unit tests")
    assert row["perfect"] is True
    explain = run("[Sprint 19][BE] Matching: Explanation summary")
    assert "Match score" in explain["summary"]


def test_upsert_collapses_greenhouse_and_lever():
    row = run("[Sprint 19][BE] Job Sources: Upsert with dedupe")
    assert row["unique"] == 1
    assert row["duplicates"] == 1
    fp = run("[Sprint 19][BE] Source Ingestion: Dedupe fingerprint generator")
    assert fp["namespaceOmitsSource"] is True


def test_company_allow_deny_and_keyword_filter():
    from app.sprint19.kanban import company_lists

    assert company_lists(company="Acme")["allowed"] is True
    assert company_lists(company="Spamcorp")["allowed"] is False
    filt = run("[Sprint 19][BE] Source Ingestion: Keyword include/exclude filter")
    assert filt["excluded"] is True
    assert filt["keep"] is False


def test_health_v8_and_status_payload():
    from app.features.health import _status_payload
    from app.sprint19.ops import health_v8

    assert _status_payload()["version"] == "sprint20"
    row = health_v8()
    assert row["version"] == "sprint19"
    assert row["schema"] == "ajas.health.v8"

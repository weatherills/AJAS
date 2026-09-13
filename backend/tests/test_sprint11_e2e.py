"""Sprint 11 E2E unhappy paths: ingest→match→apply and email follow-up SLAs."""

from __future__ import annotations

from datetime import datetime, timezone

from app.auto_apply.consent_log import record as record_consent
from app.auto_apply.form_machine import next_state
from app.job_sources.hired import hired_jobs
from app.mail.interview_time import parse_interview_time
from app.mail.sla import followup_reminders
from app.mail.snooze import snooze_until
from app.mail.strip_quotes import strip_quoted
from app.mail.threading_v2 import thread_id
from app.matching.mismatch_counts import mismatch_counts


def test_e2e_ingestion_match_apply_unhappy_paths(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("FLAG_HIRED_ADAPTER", "true")
    get_settings.cache_clear()
    blocked = hired_jobs({"jobs": [{"id": "hi-1"}]}, html="<div class='g-recaptcha'></div>")
    assert blocked == []
    assert next_state("questions", "next", payload="<div class='hcaptcha'>") == "needs_manual"
    try:
        record_consent(user_id="ada", job_id="job-1", resume_id="r1", approved=False)
        raise AssertionError("consent must fail closed")
    except ValueError:
        pass
    gaps = mismatch_counts("python", "rust kubernetes")
    assert gaps["missing"]


def test_e2e_email_threading_and_followup_slas():
    tid = thread_id(conversation_id="conv-1", message_id="<m1@ajas>")
    assert tid.startswith("graph:")
    body = strip_quoted("Can we meet?\n--\nAva\n> quoted")
    parsed = parse_interview_time("Interview 2026-09-15 14:00", timezone_name="UTC")
    assert parsed["ok"] is True
    inbound = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    sla = followup_reminders(last_inbound_at=inbound, now=datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc))
    assert 24 in sla["due"] and 72 in sla["due"]
    snooze = snooze_until(now=datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc), hours=1)
    assert snooze["until"].startswith("2026-09-14T09:00:00")
    assert "meet" in body.lower()

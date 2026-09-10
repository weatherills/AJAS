"""Email Ingestion Database PRD — uniqueness, linking, delivery states."""

from __future__ import annotations

import pytest

from app.mail.errors import MailConflictError, MailValidationError
from app.mail.keys import apply_template, body_hash, unfilled_template_vars, utc_now
from app.mail.linking import JobHint, decide_link
from app.mail.memory import InMemoryEmailStore
from app.mail.models import EmailMessage, EmailThread


def test_graph_message_id_unique_per_account():
    store = InMemoryEmailStore(seed=False)
    account = store.ensure_account("u1", address="u1@ajas.dev")
    now = utc_now()
    thread = store.upsert_thread(
        EmailThread(
            email_account_id=account.id,
            user_id="u1",
            graph_conversation_id="c1",
            subject="Hello",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    msg = EmailMessage(
        email_account_id=account.id,
        email_thread_id=thread.id,
        user_id="u1",
        graph_message_id="g-1",
        internet_message_id="<a@x>",
        conversation_id="c1",
        from_address="r@x",
        to_addresses=["u1@ajas.dev"],
        subject="Hello",
        body_text="Hi",
        received_at=now,
        created_at=now,
        updated_at=now,
    )
    store.upsert_message(msg)
    clone = msg.model_copy(update={"id": "other"})
    with pytest.raises(MailConflictError):
        store.upsert_message(clone)


def test_graph_conversation_id_unique_per_account():
    store = InMemoryEmailStore(seed=False)
    account = store.ensure_account("u1", address="u1@ajas.dev")
    now = utc_now()
    store.upsert_thread(
        EmailThread(
            email_account_id=account.id,
            user_id="u1",
            graph_conversation_id="c1",
            subject="Hello",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    with pytest.raises(MailConflictError):
        store.upsert_thread(
            EmailThread(
                email_account_id=account.id,
                user_id="u1",
                graph_conversation_id="c1",
                subject="Other",
                last_message_at=now,
                created_at=now,
                updated_at=now,
            )
        )


def test_delivery_status_round_trip():
    store = InMemoryEmailStore(seed=False)
    account = store.ensure_account("u1", address="u1@ajas.dev")
    now = utc_now()
    thread = store.upsert_thread(
        EmailThread(
            email_account_id=account.id,
            user_id="u1",
            graph_conversation_id="c2",
            subject="Hi",
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    msg = store.upsert_message(
        EmailMessage(
            email_account_id=account.id,
            email_thread_id=thread.id,
            user_id="u1",
            graph_message_id="g-2",
            internet_message_id="<b@x>",
            conversation_id="c2",
            from_address="u1@ajas.dev",
            to_addresses=["r@x"],
            subject="Hi",
            body_text="Sent",
            received_at=now,
            delivery_status="sent",
            is_incoming=False,
            created_at=now,
            updated_at=now,
        )
    )
    assert msg.delivery_status == "sent"
    assert msg.body_hash == body_hash("Sent", None)


def test_link_and_unlink_updates_source():
    store = InMemoryEmailStore(seed=False)
    account = store.seed_demo_mailbox("u1", jobs=[{"id": "job-1", "title": "Staff Engineer", "company": "Acme"}])
    threads = store.list_threads(account.id)
    linked = next(item for item in threads if item.job_posting_id)
    assert linked.link_source in {"auto", "rule", "manual"}
    assert 0 <= (linked.link_confidence or 0) <= 100
    store.unlink_thread(linked.id)
    assert store.get_thread(linked.id).job_posting_id is None
    store.link_thread(linked.id, job_posting_id="job-1", job_title="Staff Engineer", job_company="Acme", source="manual", confidence=100)
    assert store.get_thread(linked.id).link_source == "manual"


def test_user_id_required():
    store = InMemoryEmailStore(seed=False)
    with pytest.raises(MailValidationError):
        store.ensure_account("  ", address="x@y")


def test_template_fill_and_unfilled():
    filled = apply_template("Hi {firstName} at {company}", {"firstName": "Maya", "company": "Acme"})
    assert filled == "Hi Maya at Acme"
    leftover = apply_template("Hi {firstName} {role}", {"firstName": "Maya"})
    assert unfilled_template_vars(leftover) == ["role"]


def test_linking_priority_conversation_then_headers_then_tokens():
    now = utc_now()
    jobs = [
        JobHint(id="j1", title="Staff Engineer", company="Acme", contacts=["maya@acme.test"], tokens=["JOB-SE-1"]),
        JobHint(id="j2", title="Data Analyst", company="Globex", contacts=["priya@globex.test"], tokens=[]),
    ]
    existing = EmailThread(
        email_account_id="a",
        user_id="u",
        graph_conversation_id="c",
        subject="Re",
        job_posting_id="j1",
        last_message_at=now,
        created_at=now,
        updated_at=now,
    )
    msg = EmailMessage(
        email_account_id="a",
        email_thread_id="t",
        user_id="u",
        graph_message_id="g",
        internet_message_id="<n@x>",
        conversation_id="c",
        from_address="maya@acme.test",
        to_addresses=["u@x"],
        subject="Hello",
        body_text="Hi",
        received_at=now,
        created_at=now,
        updated_at=now,
    )
    first = decide_link(msg, existing_thread=existing, referenced_thread=None, jobs=jobs, auto_threshold=0.85)
    assert first.job and first.job.id == "j1"
    assert first.source == "rule"
    token_msg = msg.model_copy(update={"from_address": "other@x", "subject": "Staff Engineer at Acme (JOB-SE-1)"})
    token = decide_link(token_msg, existing_thread=None, referenced_thread=None, jobs=jobs, auto_threshold=0.85)
    assert token.job and token.job.id == "j1"
    unknown = decide_link(
        msg.model_copy(update={"from_address": "noreply@zzz", "subject": "Thanks for applying", "body_text": "generic"}),
        existing_thread=None,
        referenced_thread=None,
        jobs=jobs,
        auto_threshold=0.85,
    )
    assert unknown.job is None

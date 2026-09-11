"""In-memory EmailStore — rule engine for the Database PRD."""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta

from app.mail.constants import DEMO_MAILBOX, DEMO_USER_ID, SYSTEM_TEMPLATES
from app.mail.errors import MailConflictError, MailNotFoundError, MailValidationError
from app.mail.keys import body_hash, hours_ago, new_id, parse_ts, snippet_of, utc_now
from app.mail.models import (
    EmailAccount,
    EmailAttachment,
    EmailDraft,
    EmailIngestionEvent,
    EmailMessage,
    EmailRecipient,
    EmailThread,
    GraphSubscription,
    GraphSyncCursor,
    LinkAudit,
    ReplyIdempotency,
    SuggestionUse,
)


class InMemoryEmailStore:
    def __init__(self, *, seed: bool = False) -> None:
        self._accounts: dict[str, EmailAccount] = {}
        self._accounts_by_user: dict[str, str] = {}
        self._threads: dict[str, EmailThread] = {}
        self._messages: dict[str, EmailMessage] = {}
        self._recipients: dict[str, EmailRecipient] = {}
        self._attachments: dict[str, EmailAttachment] = {}
        self._drafts: dict[str, EmailDraft] = {}
        self._cursors: dict[str, GraphSyncCursor] = {}
        self._subscriptions: dict[str, GraphSubscription] = {}
        self._events: dict[str, EmailIngestionEvent] = {}
        self._audits: dict[str, LinkAudit] = {}
        self._idempotency: dict[str, ReplyIdempotency] = {}
        self._suggestions: dict[str, SuggestionUse] = {}
        self._blobs: dict[str, bytes] = {}
        if seed:
            self.seed_demo_mailbox(DEMO_USER_ID)

    def ensure_account(self, user_id: str, *, address: str, demo: bool = False) -> EmailAccount:
        if not user_id or not user_id.strip():
            raise MailValidationError("user_id is required", path="user_id")
        existing_id = self._accounts_by_user.get(user_id)
        if existing_id:
            return deepcopy(self._accounts[existing_id])
        now = utc_now()
        row = EmailAccount(
            user_id=user_id,
            address=address,
            demo=demo,
            connected=True,
            created_at=now,
            updated_at=now,
        )
        self._accounts[row.id] = row
        self._accounts_by_user[user_id] = row.id
        return deepcopy(row)

    def get_account(self, account_id: str) -> EmailAccount:
        row = self._accounts.get(account_id)
        if row is None:
            raise MailNotFoundError(account_id)
        return deepcopy(row)

    def get_account_for_user(self, user_id: str) -> EmailAccount | None:
        account_id = self._accounts_by_user.get(user_id)
        if not account_id:
            return None
        return deepcopy(self._accounts[account_id])

    def list_accounts(self) -> list[EmailAccount]:
        return [deepcopy(row) for row in self._accounts.values()]

    def touch_sync(self, account_id: str, *, error: str | None = None) -> EmailAccount:
        row = self._require_account(account_id)
        row.last_synced_at = utc_now()
        row.last_sync_error = error
        row.updated_at = row.last_synced_at
        return deepcopy(row)

    def get_thread(self, thread_id: str) -> EmailThread:
        row = self._threads.get(thread_id)
        if row is None:
            raise MailNotFoundError(thread_id)
        return deepcopy(row)

    def get_thread_by_conversation(self, account_id: str, conversation_id: str) -> EmailThread | None:
        for row in self._threads.values():
            if row.email_account_id == account_id and row.graph_conversation_id == conversation_id:
                return deepcopy(row)
        return None

    def list_threads(
        self,
        account_id: str,
        *,
        job_id: str | None = None,
        unlinked_only: bool = False,
    ) -> list[EmailThread]:
        rows = [row for row in self._threads.values() if row.email_account_id == account_id]
        if job_id:
            rows = [row for row in rows if row.job_posting_id == job_id]
        if unlinked_only:
            rows = [row for row in rows if not row.job_posting_id and not row.application_id]
        rows.sort(key=lambda item: item.last_message_at, reverse=True)
        return [deepcopy(row) for row in rows]

    def upsert_thread(self, thread: EmailThread) -> EmailThread:
        existing = self.get_thread_by_conversation(thread.email_account_id, thread.graph_conversation_id)
        if existing and existing.id != thread.id:
            raise MailConflictError("graph_conversation_id already exists for this account")
        now = utc_now()
        thread.updated_at = now
        if not thread.created_at:
            thread.created_at = now
        self._threads[thread.id] = thread
        return deepcopy(thread)

    def get_message(self, message_id: str) -> EmailMessage:
        row = self._messages.get(message_id)
        if row is None:
            raise MailNotFoundError(message_id)
        return deepcopy(row)

    def get_by_graph_id(self, account_id: str, graph_message_id: str) -> EmailMessage | None:
        for row in self._messages.values():
            if row.email_account_id == account_id and row.graph_message_id == graph_message_id:
                return deepcopy(row)
        return None

    def get_by_internet_id(self, user_id: str, internet_message_id: str) -> EmailMessage | None:
        if not internet_message_id:
            return None
        for row in self._messages.values():
            if row.user_id == user_id and row.internet_message_id == internet_message_id:
                return deepcopy(row)
        return None

    def list_messages(self, thread_id: str) -> list[EmailMessage]:
        rows = [row for row in self._messages.values() if row.email_thread_id == thread_id and not row.is_deleted]
        rows.sort(key=lambda item: item.received_at)
        return [deepcopy(row) for row in rows]

    def upsert_message(self, message: EmailMessage) -> EmailMessage:
        dup = self.get_by_graph_id(message.email_account_id, message.graph_message_id)
        if dup and dup.id != message.id:
            raise MailConflictError("graph_message_id already exists for this account")
        now = utc_now()
        message.updated_at = now
        if not message.created_at:
            message.created_at = now
        if not message.body_hash:
            message.body_hash = body_hash(message.body_text, message.body_html)
        if not message.snippet:
            message.snippet = snippet_of(message.body_text)
        self._messages[message.id] = message
        self._sync_thread_rollups(message.email_thread_id)
        return deepcopy(message)

    def add_recipient(self, recipient: EmailRecipient) -> EmailRecipient:
        self._recipients[recipient.id] = recipient
        return deepcopy(recipient)

    def add_attachment(self, attachment: EmailAttachment) -> EmailAttachment:
        self._attachments[attachment.id] = attachment
        return deepcopy(attachment)

    def list_attachments(self, message_id: str) -> list[EmailAttachment]:
        return [deepcopy(row) for row in self._attachments.values() if row.email_message_id == message_id]

    def get_attachment(self, attachment_id: str) -> EmailAttachment:
        row = self._attachments.get(attachment_id)
        if row is None:
            from app.mail.errors import MailNotFoundError

            raise MailNotFoundError(attachment_id)
        return deepcopy(row)

    def put_blob(self, path: str, content: bytes) -> None:
        self._blobs[path] = content

    def get_blob(self, path: str) -> bytes | None:
        return self._blobs.get(path)

    def record_event(self, event: EmailIngestionEvent) -> EmailIngestionEvent:
        self._events[event.id] = event
        return deepcopy(event)

    def event_exists(self, account_id: str, *, graph_message_id: str | None, internet_message_id: str | None) -> bool:
        for row in self._events.values():
            if row.email_account_id != account_id:
                continue
            if graph_message_id and row.graph_message_id == graph_message_id and row.status == "persisted":
                return True
            if internet_message_id and row.internet_message_id == internet_message_id and row.status == "persisted":
                return True
        return False

    def upsert_cursor(self, cursor: GraphSyncCursor) -> GraphSyncCursor:
        self._cursors[cursor.email_account_id] = cursor
        return deepcopy(cursor)

    def get_cursor(self, account_id: str) -> GraphSyncCursor | None:
        row = self._cursors.get(account_id)
        return deepcopy(row) if row else None

    def upsert_subscription(self, sub: GraphSubscription) -> GraphSubscription:
        self._subscriptions[sub.email_account_id] = sub
        return deepcopy(sub)

    def get_subscription(self, account_id: str) -> GraphSubscription | None:
        row = self._subscriptions.get(account_id)
        return deepcopy(row) if row else None

    def record_audit(self, audit: LinkAudit) -> LinkAudit:
        self._audits[audit.id] = audit
        return deepcopy(audit)

    def list_audits(self, thread_id: str) -> list[LinkAudit]:
        return [deepcopy(row) for row in self._audits.values() if row.thread_id == thread_id]

    def put_idempotency(self, row: ReplyIdempotency) -> ReplyIdempotency:
        self._idempotency[row.id] = row
        return deepcopy(row)

    def get_idempotency(self, key: str) -> ReplyIdempotency | None:
        row = self._idempotency.get(key)
        return deepcopy(row) if row else None

    def record_suggestion(self, row: SuggestionUse) -> SuggestionUse:
        self._suggestions[row.id] = row
        return deepcopy(row)

    def suggestion_count_today(self, thread_id: str, *, now: str | None = None) -> int:
        stamp = parse_ts(now or utc_now())
        start = stamp.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        count = 0
        for row in self._suggestions.values():
            if row.thread_id != thread_id:
                continue
            when = parse_ts(row.created_at)
            if start <= when < end:
                count += 1
        return count

    def mark_thread_read(self, thread_id: str) -> EmailThread:
        for row in self._messages.values():
            if row.email_thread_id == thread_id:
                row.is_read = True
                row.updated_at = utc_now()
        self._sync_thread_rollups(thread_id)
        return self.get_thread(thread_id)

    def link_thread(
        self,
        thread_id: str,
        *,
        job_posting_id: str | None,
        job_title: str | None,
        job_company: str | None,
        source: str,
        confidence: int,
        application_id: str | None = None,
    ) -> EmailThread:
        row = self._require_thread(thread_id)
        row.job_posting_id = job_posting_id
        row.application_id = application_id
        row.job_title = job_title
        row.job_company = job_company
        row.link_source = source  # type: ignore[assignment]
        row.link_confidence = max(0, min(100, confidence))
        row.updated_at = utc_now()
        return deepcopy(row)

    def unlink_thread(self, thread_id: str) -> EmailThread:
        row = self._require_thread(thread_id)
        row.job_posting_id = None
        row.application_id = None
        row.job_title = None
        row.job_company = None
        row.link_source = None
        row.link_confidence = None
        row.updated_at = utc_now()
        return deepcopy(row)

    def templates(self) -> list[dict[str, str]]:
        return [dict(item) for item in SYSTEM_TEMPLATES]

    def seed_demo_mailbox(self, user_id: str, *, jobs: list[dict] | None = None) -> EmailAccount:
        account = self.ensure_account(user_id, address=DEMO_MAILBOX, demo=True)
        if any(row.email_account_id == account.id for row in self._threads.values()):
            return account
        job_staff, job_analyst = _pick_demo_jobs(jobs)
        now = utc_now()
        staff = self._seed_thread(
            account,
            conversation_id="conv-staff-acme",
            subject="Staff Engineer at Acme (JOB-SE-1)",
            job_id=job_staff["id"] if job_staff else None,
            job_title=job_staff["title"] if job_staff else "Staff Engineer",
            job_company=job_staff["company"] if job_staff else "Acme",
            link_source="rule",
            confidence=96,
            recruiter=("maya@acme.test", "Maya Chen"),
            inbound_body="Hi — we would like to talk about the Staff Engineer role at Acme (JOB-SE-1). Are you open to a screen this week?",
            hours=26,
        )
        self._add_outbound(
            account,
            staff,
            body="Thanks Maya, I am interested in Staff Engineer at Acme and can make Thursday afternoon.",
            hours=20,
        )
        self._seed_thread(
            account,
            conversation_id="conv-analyst-globex",
            subject="Data Analyst at Globex",
            job_id=job_analyst["id"] if job_analyst else None,
            job_title=job_analyst["title"] if job_analyst else "Data Analyst",
            job_company=job_analyst["company"] if job_analyst else "Globex",
            link_source="rule",
            confidence=90,
            recruiter=("priya@globex.test", "Priya Shah"),
            inbound_body="Thanks for applying to Data Analyst at Globex. Could you send a portfolio sample?",
            hours=8,
        )
        self._seed_thread(
            account,
            conversation_id="conv-unlinked-generic",
            subject="Thanks for applying",
            job_id=None,
            job_title=None,
            job_company=None,
            link_source=None,
            confidence=0,
            recruiter=("noreply@careers-unknown.test", "Talent Team"),
            inbound_body="We received your application and will be in touch if there is a fit.",
            hours=3,
            unread=True,
        )
        account.last_synced_at = now
        account.updated_at = now
        self._accounts[account.id] = account
        return deepcopy(account)

    def _seed_thread(
        self,
        account: EmailAccount,
        *,
        conversation_id: str,
        subject: str,
        job_id: str | None,
        job_title: str | None,
        job_company: str | None,
        link_source: str | None,
        confidence: int,
        recruiter: tuple[str, str],
        inbound_body: str,
        hours: float,
        unread: bool = False,
    ) -> EmailThread:
        now = utc_now()
        received = hours_ago(hours, now=now)
        thread = EmailThread(
            email_account_id=account.id,
            user_id=account.user_id,
            graph_conversation_id=conversation_id,
            subject=subject,
            job_posting_id=job_id,
            job_title=job_title,
            job_company=job_company,
            link_source=link_source,  # type: ignore[arg-type]
            link_confidence=confidence if job_id else None,
            last_message_at=received,
            unread_count=1 if unread else 0,
            snippet=snippet_of(inbound_body),
            participants=[recruiter[0], account.address],
            created_at=now,
            updated_at=now,
        )
        self._threads[thread.id] = thread
        message = EmailMessage(
            email_account_id=account.id,
            email_thread_id=thread.id,
            user_id=account.user_id,
            graph_message_id=f"g-{conversation_id}-1",
            internet_message_id=f"<{conversation_id}-1@mail.test>",
            conversation_id=conversation_id,
            from_address=recruiter[0],
            from_name=recruiter[1],
            to_addresses=[account.address],
            subject=subject,
            body_text=inbound_body,
            received_at=received,
            is_incoming=True,
            is_read=not unread,
            delivery_status="received",
            created_at=now,
            updated_at=now,
        )
        self.upsert_message(message)
        self.add_recipient(
            EmailRecipient(
                email_account_id=account.id,
                email_message_id=message.id,
                kind="from",
                address=recruiter[0],
                name=recruiter[1],
            )
        )
        return thread

    def _add_outbound(self, account: EmailAccount, thread: EmailThread, *, body: str, hours: float) -> EmailMessage:
        now = utc_now()
        sent_at = hours_ago(hours, now=now)
        message = EmailMessage(
            email_account_id=account.id,
            email_thread_id=thread.id,
            user_id=account.user_id,
            graph_message_id=f"g-{thread.graph_conversation_id}-out",
            internet_message_id=f"<{thread.graph_conversation_id}-out@ajas.dev>",
            conversation_id=thread.graph_conversation_id,
            from_address=account.address,
            from_name="Local User",
            to_addresses=[p for p in thread.participants if p != account.address] or ["maya@acme.test"],
            subject=f"Re: {thread.subject}",
            body_text=body,
            received_at=sent_at,
            sent_at=sent_at,
            is_incoming=False,
            is_read=True,
            delivery_status="sent",
            created_at=now,
            updated_at=now,
        )
        return self.upsert_message(message)

    def _sync_thread_rollups(self, thread_id: str) -> None:
        thread = self._threads.get(thread_id)
        if thread is None:
            return
        messages = [row for row in self._messages.values() if row.email_thread_id == thread_id and not row.is_deleted]
        if not messages:
            return
        latest = max(messages, key=lambda item: item.received_at)
        thread.last_message_at = latest.received_at
        thread.snippet = latest.snippet or snippet_of(latest.body_text)
        thread.unread_count = sum(1 for item in messages if item.is_incoming and not item.is_read)
        people: list[str] = []
        for item in messages:
            for addr in [item.from_address, *item.to_addresses]:
                if addr and addr not in people:
                    people.append(addr)
        thread.participants = people
        thread.updated_at = utc_now()

    def _require_account(self, account_id: str) -> EmailAccount:
        row = self._accounts.get(account_id)
        if row is None:
            raise MailNotFoundError(account_id)
        return row

    def _require_thread(self, thread_id: str) -> EmailThread:
        row = self._threads.get(thread_id)
        if row is None:
            raise MailNotFoundError(thread_id)
        return row


def _pick_demo_jobs(jobs: list[dict] | None) -> tuple[dict | None, dict | None]:
    rows = jobs or []
    staff = next((item for item in rows if "staff engineer" in (item.get("title") or "").lower()), None)
    analyst = next((item for item in rows if "data analyst" in (item.get("title") or "").lower()), None)
    return staff, analyst

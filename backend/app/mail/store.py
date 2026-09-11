"""Email store protocol and factory."""

from __future__ import annotations

from typing import Protocol

from app.mail.models import (
    EmailAccount,
    EmailAttachment,
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


class EmailStore(Protocol):
    def ensure_account(self, user_id: str, *, address: str, demo: bool = False) -> EmailAccount: ...

    def get_account(self, account_id: str) -> EmailAccount: ...

    def get_account_for_user(self, user_id: str) -> EmailAccount | None: ...

    def list_accounts(self) -> list[EmailAccount]: ...

    def touch_sync(self, account_id: str, *, error: str | None = None) -> EmailAccount: ...

    def get_thread(self, thread_id: str) -> EmailThread: ...

    def get_thread_by_conversation(self, account_id: str, conversation_id: str) -> EmailThread | None: ...

    def list_threads(
        self,
        account_id: str,
        *,
        job_id: str | None = None,
        unlinked_only: bool = False,
    ) -> list[EmailThread]: ...

    def upsert_thread(self, thread: EmailThread) -> EmailThread: ...

    def get_message(self, message_id: str) -> EmailMessage: ...

    def get_by_graph_id(self, account_id: str, graph_message_id: str) -> EmailMessage | None: ...

    def get_by_internet_id(self, user_id: str, internet_message_id: str) -> EmailMessage | None: ...

    def list_messages(self, thread_id: str) -> list[EmailMessage]: ...

    def upsert_message(self, message: EmailMessage) -> EmailMessage: ...

    def add_recipient(self, recipient: EmailRecipient) -> EmailRecipient: ...

    def add_attachment(self, attachment: EmailAttachment) -> EmailAttachment: ...

    def list_attachments(self, message_id: str) -> list[EmailAttachment]: ...

    def get_attachment(self, attachment_id: str) -> EmailAttachment: ...

    def put_blob(self, path: str, content: bytes) -> None: ...

    def get_blob(self, path: str) -> bytes | None: ...

    def record_event(self, event: EmailIngestionEvent) -> EmailIngestionEvent: ...

    def event_exists(
        self, account_id: str, *, graph_message_id: str | None, internet_message_id: str | None
    ) -> bool: ...

    def upsert_cursor(self, cursor: GraphSyncCursor) -> GraphSyncCursor: ...

    def get_cursor(self, account_id: str) -> GraphSyncCursor | None: ...

    def upsert_subscription(self, sub: GraphSubscription) -> GraphSubscription: ...

    def get_subscription(self, account_id: str) -> GraphSubscription | None: ...

    def record_audit(self, audit: LinkAudit) -> LinkAudit: ...

    def list_audits(self, thread_id: str) -> list[LinkAudit]: ...

    def put_idempotency(self, row: ReplyIdempotency) -> ReplyIdempotency: ...

    def get_idempotency(self, key: str) -> ReplyIdempotency | None: ...

    def record_suggestion(self, row: SuggestionUse) -> SuggestionUse: ...

    def suggestion_count_today(self, thread_id: str, *, now: str | None = None) -> int: ...

    def mark_thread_read(self, thread_id: str) -> EmailThread: ...

    def link_thread(self, thread_id: str, **kwargs) -> EmailThread: ...

    def unlink_thread(self, thread_id: str) -> EmailThread: ...

    def templates(self) -> list[dict[str, str]]: ...

    def seed_demo_mailbox(self, user_id: str, *, jobs: list[dict] | None = None) -> EmailAccount: ...


_store: EmailStore | None = None


def get_email_store() -> EmailStore:
    global _store
    if _store is not None:
        return _store
    from app.config import get_settings
    from app.mail.memory import InMemoryEmailStore

    settings = get_settings()
    if not settings.cosmos_connection_string:
        _store = InMemoryEmailStore(seed=False)
        return _store
    from app.mail.cosmos_store import CosmosEmailStore
    from app.storage.cosmos import get_database

    _store = CosmosEmailStore(get_database())
    return _store


def set_email_store(store: EmailStore | None) -> None:
    global _store
    _store = store

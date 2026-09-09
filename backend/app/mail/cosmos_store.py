"""Cosmos DB implementation of EmailStore."""

from __future__ import annotations

from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.mail.constants import (
    ACCOUNTS_CONTAINER,
    ATTACHMENTS_CONTAINER,
    AUDITS_CONTAINER,
    CURSORS_CONTAINER,
    DRAFTS_CONTAINER,
    EVENTS_CONTAINER,
    MESSAGES_CONTAINER,
    RECIPIENTS_CONTAINER,
    SUBSCRIPTIONS_CONTAINER,
    THREADS_CONTAINER,
)
from app.mail.memory import InMemoryEmailStore
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


class CosmosEmailStore:
    def __init__(self, database: Any) -> None:
        self._accounts = database.get_container_client(ACCOUNTS_CONTAINER)
        self._threads = database.get_container_client(THREADS_CONTAINER)
        self._messages = database.get_container_client(MESSAGES_CONTAINER)
        self._recipients = database.get_container_client(RECIPIENTS_CONTAINER)
        self._attachments = database.get_container_client(ATTACHMENTS_CONTAINER)
        self._drafts = database.get_container_client(DRAFTS_CONTAINER)
        self._cursors = database.get_container_client(CURSORS_CONTAINER)
        self._subscriptions = database.get_container_client(SUBSCRIPTIONS_CONTAINER)
        self._events = database.get_container_client(EVENTS_CONTAINER)
        self._audits = database.get_container_client(AUDITS_CONTAINER)
        self._working_extras = database.get_container_client(DRAFTS_CONTAINER)

    def __getattr__(self, name: str):
        def wrapper(*args, **kwargs):
            working = self._hydrate()
            result = getattr(working, name)(*args, **kwargs)
            if name.startswith("get_") or name.startswith("list_") or name in {
                "event_exists",
                "suggestion_count_today",
                "templates",
                "get_blob",
            }:
                return result
            self._persist_working(working)
            return result

        if name.startswith("_"):
            raise AttributeError(name)
        return wrapper

    def _all_items(self, client: Any) -> list[dict]:
        try:
            return list(client.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))
        except TypeError:
            return list(client.query_items(query="SELECT * FROM c"))

    def _hydrate(self) -> InMemoryEmailStore:
        working = InMemoryEmailStore(seed=False)
        accounts = [EmailAccount.model_validate(item) for item in self._all_items(self._accounts)]
        working._accounts = {row.id: row for row in accounts}
        working._accounts_by_user = {row.user_id: row.id for row in accounts}
        working._threads = {row.id: row for row in (EmailThread.model_validate(i) for i in self._all_items(self._threads))}
        working._messages = {
            row.id: row for row in (EmailMessage.model_validate(i) for i in self._all_items(self._messages))
        }
        working._recipients = {
            row.id: row for row in (EmailRecipient.model_validate(i) for i in self._all_items(self._recipients))
        }
        working._attachments = {
            row.id: row for row in (EmailAttachment.model_validate(i) for i in self._all_items(self._attachments))
        }
        working._drafts = {row.id: row for row in (EmailDraft.model_validate(i) for i in self._all_items(self._drafts))}
        working._cursors = {
            row.email_account_id: row
            for row in (GraphSyncCursor.model_validate(i) for i in self._all_items(self._cursors))
        }
        working._subscriptions = {
            row.email_account_id: row
            for row in (GraphSubscription.model_validate(i) for i in self._all_items(self._subscriptions))
        }
        working._events = {
            row.id: row for row in (EmailIngestionEvent.model_validate(i) for i in self._all_items(self._events))
        }
        working._audits = {row.id: row for row in (LinkAudit.model_validate(i) for i in self._all_items(self._audits))}
        extras = [item for item in self._all_items(self._working_extras) if item.get("kind") in {"idempotency", "suggestion"}]
        for item in extras:
            if item.get("kind") == "idempotency":
                row = ReplyIdempotency.model_validate(item)
                working._idempotency[row.id] = row
            elif item.get("kind") == "suggestion":
                row = SuggestionUse.model_validate(item)
                working._suggestions[row.id] = row
        return working

    def _upsert(self, client: Any, payload: dict) -> None:
        try:
            client.replace_item(item=payload["id"], body=payload)
        except CosmosResourceNotFoundError:
            client.create_item(body=payload)

    def _persist_working(self, working: InMemoryEmailStore) -> None:
        for row in working._accounts.values():
            self._upsert(self._accounts, row.model_dump())
        for row in working._threads.values():
            self._upsert(self._threads, row.model_dump())
        for row in working._messages.values():
            self._upsert(self._messages, row.model_dump())
        for row in working._recipients.values():
            self._upsert(self._recipients, row.model_dump())
        for row in working._attachments.values():
            self._upsert(self._attachments, row.model_dump())
        for row in working._drafts.values():
            self._upsert(self._drafts, row.model_dump())
        for row in working._cursors.values():
            self._upsert(self._cursors, row.model_dump())
        for row in working._subscriptions.values():
            self._upsert(self._subscriptions, row.model_dump())
        for row in working._events.values():
            self._upsert(self._events, row.model_dump())
        for row in working._audits.values():
            self._upsert(self._audits, row.model_dump())
        for row in working._idempotency.values():
            payload = row.model_dump()
            payload["kind"] = "idempotency"
            self._upsert(self._working_extras, payload)
        for row in working._suggestions.values():
            payload = row.model_dump()
            payload["kind"] = "suggestion"
            self._upsert(self._working_extras, payload)

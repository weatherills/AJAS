"""Email Ingestion & Reply database constants (Database PRD)."""

from typing import Final, Literal

DeliveryStatus = Literal["received", "queued", "sending", "sent", "failed", "draft", "bounced", "deferred"]
LinkSource = Literal["auto", "manual", "rule"]
AttachmentStatus = Literal["stored", "skipped_oversize", "skipped_scan", "pending"]
SyncMode = Literal["webhook", "poll", "both"]

DELIVERY_STATUSES: Final[frozenset[str]] = frozenset(
    {"received", "queued", "sending", "sent", "failed", "draft", "bounced", "deferred"}
)
LINK_SOURCES: Final[frozenset[str]] = frozenset({"auto", "manual", "rule"})
TEMPLATE_VARS: Final[tuple[str, ...]] = ("firstName", "company", "role", "jobRef")

ACCOUNTS_CONTAINER: Final[str] = "email_accounts"
THREADS_CONTAINER: Final[str] = "email_threads"
MESSAGES_CONTAINER: Final[str] = "email_messages"
RECIPIENTS_CONTAINER: Final[str] = "email_recipients"
ATTACHMENTS_CONTAINER: Final[str] = "email_attachments"
DRAFTS_CONTAINER: Final[str] = "email_drafts"
CURSORS_CONTAINER: Final[str] = "graph_sync_cursors"
SUBSCRIPTIONS_CONTAINER: Final[str] = "graph_subscriptions"
EVENTS_CONTAINER: Final[str] = "email_ingestion_events"
AUDITS_CONTAINER: Final[str] = "email_link_audits"
TEMPLATES_CONTAINER: Final[str] = "email_templates"

ACCOUNT_PK: Final[str] = "/id"
PARTITION_PK: Final[str] = "/email_account_id"

DEMO_USER_ID: Final[str] = "local-user"
DEMO_MAILBOX: Final[str] = "local-user@ajas.dev"

SYSTEM_TEMPLATES: Final[tuple[dict[str, str], ...]] = (
    {
        "id": "thanks",
        "name": "Thanks",
        "body": "Hi {firstName},\n\nThanks for reaching out about the {role} role at {company} ({jobRef}). I'm interested and happy to share more.\n\nBest regards",
    },
    {
        "id": "followup",
        "name": "Follow-up",
        "body": "Hi {firstName},\n\nJust following up on the {role} role at {company} ({jobRef}). Happy to jump on a call this week.\n\nBest regards",
    },
    {
        "id": "availability",
        "name": "Availability",
        "body": "Hi {firstName},\n\nI'm available to talk about the {role} role at {company} ({jobRef}). What times work on your side?\n\nBest regards",
    },
)


def _policy(*composites: list[dict]) -> dict:
    return {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": "/\"_etag\"/?"}],
        "compositeIndexes": list(composites),
    }


THREADS_INDEXING: Final[dict] = _policy(
    [
        {"path": "/email_account_id", "order": "ascending"},
        {"path": "/last_message_at", "order": "descending"},
    ],
    [{"path": "/graph_conversation_id", "order": "ascending"}],
    [{"path": "/job_posting_id", "order": "ascending"}],
)
MESSAGES_INDEXING: Final[dict] = _policy(
    [
        {"path": "/email_thread_id", "order": "ascending"},
        {"path": "/received_at", "order": "descending"},
    ],
    [{"path": "/graph_message_id", "order": "ascending"}],
    [{"path": "/delivery_status", "order": "ascending"}],
)

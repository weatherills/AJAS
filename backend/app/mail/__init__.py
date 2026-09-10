"""Email Ingestion & Reply database layer (Cosmos schema + store).

Implements the Database PRD: threads, messages, drafts, attachments,
Graph sync cursors/subscriptions, and ingestion events. Partition key is
email_account_id. The in-memory store is the rule engine; Cosmos hydrates
and persists the same documents.
"""

from app.mail.constants import THREADS_CONTAINER
from app.mail.containers import container_specs, ensure_mail_containers
from app.mail.errors import (
    MailConflictError,
    MailNotFoundError,
    MailStoreError,
    MailValidationError,
)
from app.mail.memory import InMemoryEmailStore
from app.mail.models import EmailAccount, EmailMessage, EmailThread
from app.mail.store import EmailStore, get_email_store

__all__ = [
    "THREADS_CONTAINER",
    "EmailAccount",
    "EmailMessage",
    "EmailStore",
    "EmailThread",
    "InMemoryEmailStore",
    "MailConflictError",
    "MailNotFoundError",
    "MailStoreError",
    "MailValidationError",
    "container_specs",
    "ensure_mail_containers",
    "get_email_store",
]

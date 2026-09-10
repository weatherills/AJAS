"""Pydantic documents for Email Ingestion Cosmos containers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.mail.constants import AttachmentStatus, DeliveryStatus, LinkSource, SyncMode
from app.mail.keys import new_id


class EmailAccount(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    user_id: str
    address: str
    provider: str = "microsoft365"
    connected: bool = True
    last_synced_at: str | None = None
    last_sync_error: str | None = None
    demo: bool = False
    created_at: str
    updated_at: str


class EmailThread(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    user_id: str
    graph_conversation_id: str
    subject: str
    job_posting_id: str | None = None
    application_id: str | None = None
    job_title: str | None = None
    job_company: str | None = None
    link_source: LinkSource | None = None
    link_confidence: int | None = None
    last_message_at: str
    unread_count: int = 0
    snippet: str = ""
    participants: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class EmailMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    email_thread_id: str
    user_id: str
    graph_message_id: str
    internet_message_id: str
    conversation_id: str
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    from_address: str
    from_name: str = ""
    to_addresses: list[str] = Field(default_factory=list)
    cc_addresses: list[str] = Field(default_factory=list)
    bcc_addresses: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    body_html: str | None = None
    snippet: str = ""
    body_hash: str = ""
    received_at: str
    sent_at: str | None = None
    is_incoming: bool = True
    is_read: bool = False
    is_deleted: bool = False
    deleted_at: str | None = None
    has_attachments: bool = False
    delivery_status: DeliveryStatus = "received"
    etag: str | None = None
    created_at: str
    updated_at: str


class EmailRecipient(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    email_message_id: str
    kind: str
    address: str
    name: str = ""


class EmailAttachment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    email_message_id: str
    user_id: str
    file_name: str
    size: int
    content_type: str
    sha256: str | None = None
    blob_path: str | None = None
    is_inline: bool = False
    content_id: str | None = None
    status: AttachmentStatus = "stored"
    skip_reason: str | None = None


class EmailDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    email_thread_id: str
    user_id: str
    body_text: str = ""
    template_id: str | None = None
    ai_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "open"
    created_at: str
    updated_at: str


class GraphSyncCursor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    mode: SyncMode = "both"
    delta_token: str | None = None
    updated_at: str


class GraphSubscription(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    graph_subscription_id: str
    resource: str = "/me/messages"
    expires_at: str
    client_state: str
    created_at: str


class EmailIngestionEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    graph_message_id: str | None = None
    internet_message_id: str | None = None
    status: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class LinkAudit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    email_account_id: str
    thread_id: str
    message_id: str | None = None
    method: LinkSource
    score: float | None = None
    job_posting_id: str | None = None
    actor: str
    created_at: str


class ReplyIdempotency(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    thread_id: str
    message_id: str
    created_at: str


class SuggestionUse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_id)
    thread_id: str
    user_id: str
    created_at: str

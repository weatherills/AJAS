# Database PRD: Email Ingestion & Reply
**Feature:** Email Ingestion & Reply  
**Type:** database

## Feature: Email Ingestion & Reply — Database Schema

Supports pulling Microsoft Graph mail, linking to job/application context, composing in-app replies with templates/suggestions, and handling attachments. Optimized for Cosmos DB (serverless) with partitioning by email_account_id for most entities.

### Scope
- Persist inbound/outbound messages, threads, recipients, and attachments.
- Track Microsoft Graph sync state (polling delta tokens) and webhook subscriptions.
- Maintain association of threads to JobPosting/Application records.
- Store reply drafts, sent status, and template library.
- Event log for ingestion to ensure idempotent processing and troubleshooting.

### Key Relationships
- email_accounts 1—N email_threads, email_messages, email_drafts, graph_sync_cursors, graph_subscriptions, email_ingestion_events.
- email_threads 1—N email_messages, email_drafts; optional link to job_posting_id or application_id (external tables).
- email_messages 1—N email_recipients, email_attachments.
- email_drafts 1—N email_attachments (for unsent files).

### Behaviors & Constraints
- Uniqueness: graph_message_id and graph_conversation_id are unique per email_account_id.
- Delivery states: email_messages.delivery_status in ['received','queued','sending','sent','failed','draft'].
- Read state mirrors Graph; updates are idempotent via graph_message_id.
- Thread linking: either job_posting_id or application_id may be set (or neither); link_source in ['auto','manual','rule'] with link_confidence 0–100.
- Attachments stored in Blob; only metadata and blob references in DB. Inline attachments flagged via is_inline and content_id.
- Drafts capture AI suggestions (ai_suggestions JSON) and optional template_id; sending creates an outbound email_messages row and transitions draft status.
- Webhook+poll coexistence: graph_sync_cursors.mode indicates active strategy; ingestion deduped via email_ingestion_events and graph IDs.
- Deletions: messages marked is_deleted with deleted_at; content retained for audit unless purged by policy.

### Indexing & Partitioning (Cosmos-oriented)
- Partition key: email_account_id on email_threads, email_messages, email_drafts, email_recipients, email_attachments, graph_sync_cursors, graph_subscriptions, email_ingestion_events.
- Suggested composite/secondary indexes: (email_thread_id, received_at DESC), (graph_message_id), (graph_conversation_id), (job_posting_id | application_id on threads), (delivery_status), (last_message_at DESC).

### Edge Cases
- Large threads: paginate by received_at; maintain last_message_at on email_threads for quick retrieval.
- External deletion/move: respect Graph changeType events; if moved to Deleted Items, set is_deleted=true.
- Missing HTML: body_text is required fallback; body_html optional.
- BCC visibility: only present on outbound authored by the user; inbound BCC usually absent.

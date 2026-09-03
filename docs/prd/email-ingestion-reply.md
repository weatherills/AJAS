# Email Ingestion & Reply — Product Requirements

> **Runbook phase:** Phase 7 &nbsp;·&nbsp; **Feature key:** `email-ingestion-reply`
>
> Consolidated PRD for the "Email Ingestion & Reply" feature — combines the backend,
> database, and frontend requirements in one place. The canonical,
> CodeSpring-generated sources remain the source of truth:
> - [Backend PRD](../../.codespring/PRDs/email-ingestion-reply/backend-prd-email-ingestion-reply.md)
> - [Database PRD](../../.codespring/PRDs/email-ingestion-reply/database-prd-email-ingestion-reply.md)
> - [Frontend PRD](../../.codespring/PRDs/email-ingestion-reply/frontend-prd-email-ingestion-reply.md)

---

## Backend

### Backend PRD: Email Ingestion & Reply
**Feature:** Email Ingestion & Reply  
**Type:** backend

### Email Ingestion & Reply

#### Feature overview
Enable AJAS to ingest relevant Microsoft 365 emails for tracked job opportunities and allow users to reply from within the app. The system links messages to JobPosting/Application records, manages attachments, and provides template-based and AI-assisted reply suggestions. All interactions respect user mailbox permissions and persist complete conversation context.

#### Scope & behavior
- Permissions/auth
  - Per-user Microsoft 365 OAuth with Mail.Read, Mail.ReadWrite, Mail.Send, Offline_access.
  - Store refresh tokens encrypted; rotate/refresh transparently.
  - Only ingest and send on behalf of the authenticated user (no shared mailboxes in MVP).

- Ingestion (Microsoft Graph)
  - Primary: Webhook subscriptions on /me/messages with changeType created, updated; resourceData preferred. Renew before expiry.
  - Fallback: Timer-triggered polling (5–10 min) using delta queries if subscription fails or is not yet established.
  - Idempotency: dedupe by (userId, internetMessageId). If absent, fallback to (userId, messageId) with ETag check.
  - Only persist messages that match tracked jobs (see Thread Linking). Non-matching messages are ignored (but can be reprocessed if tracking rules change).
  - Backoff on 429/5xx with exponential delay; enqueue for retry via Storage Queues.

- Thread Linking
  - Deterministic mapping priority:
    1) Existing thread by conversationId already linked to a JobPosting/Application.
    2) In-Reply-To/References headers referencing a known message for a job.
    3) Sender/recipient match recruiter/company contacts stored on a JobPosting/Application.
    4) Subject contains tracked job tokens (e.g., jobRef, company + role) configured on the JobPosting.
  - If ambiguous (multiple candidates) or none found, mark message as Unlinked and enqueue for AI Matching Service to suggest a link score; auto-link only if score ≥ configurable threshold (default 0.85), else await manual link.
  - Maintain Thread entity grouping by (userId, conversationId) with foreign key to JobPosting or Application.

- Reply Composer
  - Send replies within an existing thread; enforce user must own original mailbox.
  - Supports template variables: {firstName}, {company}, {role}, {jobRef}. Validate presence; unfilled variables cause 422.
  - Quick suggestions via Azure OpenAI using last N (≤10) messages + job context; return 3 options with tone metadata.
  - On send, call Graph reply/forward as appropriate, set In-Reply-To/References, and persist sent message.

- Attachment Handling
  - Ingestion: fetch attachments for linked messages where size ≤ 10 MB per file and total ≤ 25 MB per message. Larger files: store metadata only and mark status=skipped_oversize.
  - Upload attachments to Azure Blob Storage (path: /users/{userId}/messages/{messageId}/) with contentType and SHA256; store metadata in Cosmos.
  - Replies can include attachments from Blob by reference; validate cumulative size limits before sending via Graph.

- Data persistence (Cosmos DB)
  - Message: id, userId, internetMessageId, graphMessageId, threadId, jobId/applicationId (nullable), from, to/cc/bcc, subject, snippet, bodyHash, receivedAt, sentAt, isIncoming, headers, hasAttachments, attachmentIds[], status.
  - Thread: id, userId, conversationId, jobId/applicationId, lastMessageAt, messageIds[].
  - Attachment: id, userId, messageId, fileName, size, contentType, sha256, blobUrl, status.
  - LinkAudit: id, messageId, method (rule/ai/manual), score, createdAt, actor.

- API endpoints (all require user auth; JSON)
  - POST /webhooks/graph/mail
    - Purpose: receive Graph notifications; validate token; enqueue message fetch tasks.
    - 202 on accepted; handles validation handshake.
  - GET /jobs/{jobId}/threads?limit&cursor
    - Returns threads linked to a job with lastMessage preview.
  - GET /threads/{threadId}/messages?limit&cursor
    - Returns ordered messages with attachment metadata.
  - POST /threads/{threadId}/reply
    - Body: { bodyText, bodyHtml?, templateId?, variables?, attachmentIds?, idempotencyKey }
    - 201 with sent message; 409 on duplicate idempotencyKey; 404 if thread not owned.
  - POST /threads/{threadId}/suggestions
    - Body: { tone?, contextNotes? }
    - Returns [{text, tone, rationale?}] within 3s target.

- Validation & errors
  - Reject sending if thread not linked to user’s mailbox or if OAuth token invalid (401/403).
  - PII safety: do not log message bodies; store bodyHash for dedupe; redact secrets in logs.
  - Rate limits: cap suggestions to 10/day/thread; return 429 when exceeded.

- Performance/SLA
  - Ingestion latency: ≤ 60s p50 from Graph event to message persisted.
  - Reply send: ≤ 3s p50 API response (excluding large attachment upload).
  - Storage/queue operations idempotent; exactly-once persistence for messages.

#### User-facing flows
- Mailbox connection (precondition): user grants Microsoft permissions; system creates/renews subscriptions.
- Ingestion:
  1) Graph notifies webhook; function enqueues fetch.
  2) Worker fetches message + attachments, dedupes, links to thread/job, persists.
- Viewing and replying:
  1) Client queries /jobs/{jobId}/threads and /threads/{threadId}/messages.
  2) Client requests /threads/{threadId}/suggestions for quick drafts.
  3) Client calls /threads/{threadId}/reply with body/attachments; system sends via Graph, persists sent message.
- Edge cases:
  - Missing conversationId: fall back to header-based linking.
  - Multiple job candidates: mark Unlinked; expose via API with link suggestions.
  - Oversized attachments: skip with status, include reason in metadata.

#### Acceptance criteria
- Webhook validation tokens are echoed; invalid signatures are rejected (401).
- Messages are not duplicated when Graph sends repeated notifications.
- Only messages matching linking rules are persisted; others are ignored or queued for AI matching.
- Threads correctly aggregate by conversationId and remain associated after new messages arrive.
- Suggestions endpoint returns three drafts ≤ 500 tokens each within 3s p50.
- Reply endpoint sends via the user’s mailbox, preserves threading headers, and stores the sent copy.
- Attachment files are stored in Blob and retrievable by secure URL; oversized files are not downloaded and flagged.
- Idempotency on reply prevents duplicate sends when idempotencyKey is reused within 24h.
- Proper error codes: 401/403 on auth issues, 404 on missing thread, 422 on invalid template variables, 429 on rate limit.
- All PII logs are redacted; message bodies are not written to logs.

#### Out of scope
- Gmail/IMAP integration, calendar scheduling, contact management.
- UI for template management beyond simple IDs/variables.
- Full antivirus/malware scanning of attachments.
- Shared mailboxes and delegated send-on-behalf scenarios.
---

## Database

### Database PRD: Email Ingestion & Reply
**Feature:** Email Ingestion & Reply  
**Type:** database

#### Feature: Email Ingestion & Reply — Database Schema

Supports pulling Microsoft Graph mail, linking to job/application context, composing in-app replies with templates/suggestions, and handling attachments. Optimized for Cosmos DB (serverless) with partitioning by email_account_id for most entities.

##### Scope
- Persist inbound/outbound messages, threads, recipients, and attachments.
- Track Microsoft Graph sync state (polling delta tokens) and webhook subscriptions.
- Maintain association of threads to JobPosting/Application records.
- Store reply drafts, sent status, and template library.
- Event log for ingestion to ensure idempotent processing and troubleshooting.

##### Key Relationships
- email_accounts 1—N email_threads, email_messages, email_drafts, graph_sync_cursors, graph_subscriptions, email_ingestion_events.
- email_threads 1—N email_messages, email_drafts; optional link to job_posting_id or application_id (external tables).
- email_messages 1—N email_recipients, email_attachments.
- email_drafts 1—N email_attachments (for unsent files).

##### Behaviors & Constraints
- Uniqueness: graph_message_id and graph_conversation_id are unique per email_account_id.
- Delivery states: email_messages.delivery_status in ['received','queued','sending','sent','failed','draft'].
- Read state mirrors Graph; updates are idempotent via graph_message_id.
- Thread linking: either job_posting_id or application_id may be set (or neither); link_source in ['auto','manual','rule'] with link_confidence 0–100.
- Attachments stored in Blob; only metadata and blob references in DB. Inline attachments flagged via is_inline and content_id.
- Drafts capture AI suggestions (ai_suggestions JSON) and optional template_id; sending creates an outbound email_messages row and transitions draft status.
- Webhook+poll coexistence: graph_sync_cursors.mode indicates active strategy; ingestion deduped via email_ingestion_events and graph IDs.
- Deletions: messages marked is_deleted with deleted_at; content retained for audit unless purged by policy.

##### Indexing & Partitioning (Cosmos-oriented)
- Partition key: email_account_id on email_threads, email_messages, email_drafts, email_recipients, email_attachments, graph_sync_cursors, graph_subscriptions, email_ingestion_events.
- Suggested composite/secondary indexes: (email_thread_id, received_at DESC), (graph_message_id), (graph_conversation_id), (job_posting_id | application_id on threads), (delivery_status), (last_message_at DESC).

##### Edge Cases
- Large threads: paginate by received_at; maintain last_message_at on email_threads for quick retrieval.
- External deletion/move: respect Graph changeType events; if moved to Deleted Items, set is_deleted=true.
- Missing HTML: body_text is required fallback; body_html optional.
- BCC visibility: only present on outbound authored by the user; inbound BCC usually absent.

---

## Frontend

### Frontend PRD: Email Ingestion & Reply
**Feature:** Email Ingestion & Reply  
**Type:** frontend

### Email Ingestion & Reply — Frontend/UI PRD

#### Feature overview
Enable users to view and respond to recruiter emails related to tracked Job Postings/Applications directly in AJAS. Surface auto-linked threads per job, show attachments, and provide a streamlined reply composer with templates and AI suggestions to accelerate communication without leaving the app.

#### Scope & behavior
- Supported mailbox: Microsoft 365 Outlook via Microsoft Graph (single connected account per user).
- Locations:
  - Job Details page: Emails tab with thread list and message view.
  - Global “Email” panel (optional entry): lists recent job-linked threads across all jobs.
- States:
  - Not connected: prompt to “Connect Microsoft 365 Email” with OAuth CTA.
  - Connected, no emails: empty state with “No emails yet. Try Refresh.”
  - Loading/syncing: spinner with last sync timestamp.
  - Error: inline banner with retry and error details (rate limit, expired token).
- Permissions/validations:
  - Only owner of the connected mailbox can view/send.
  - Reply requires non-empty body; max 25 MB total attachments; up to 20 files; supported formats shown.
- Thread linking:
  - Auto-linked threads displayed under the corresponding Job Posting/Application.
  - If message cannot be confidently linked, show “Unlinked” badge with “Link to job” control (searchable job picker); allow unlink from a job.
- Privacy/Safety:
  - Show clear “From: your@domain.com” (read-only).
  - Confirm dialog when sending to multiple recipients or with empty subject.
- Accessibility:
  - Keyboard navigation for thread list, message view, composer.
  - ARIA labels for actions; contrast AA; focus states visible.

#### User-facing flows
1. Connect email (first run)
   - User sees connect card on Emails tab.
   - Click “Connect Microsoft 365” → opens OAuth (new window).
   - On success: show initial sync in progress; threads appear progressively with timestamped “Last synced”.

2. View threads for a job
   - Emails tab shows thread list (left): each item shows subject, participants, last message snippet, relative time, unread badge.
   - Selecting a thread opens message view (right): messages in chronological order (latest at bottom), with sender, time, rich-text body, and attachments.
   - Unread messages mark as read when viewed.

3. Manual link/unlink
   - For an “Unlinked” message: click “Link to job” → modal with job search (title/company) → select → toast “Linked to [Job]”.
   - From a linked thread: overflow menu → “Unlink from job” (with confirm).

4. Reply in-app
   - Click “Reply” at bottom of thread → composer opens inline:
     - Pre-filled To/CC from last message; Subject prefixed “Re:”.
     - Rich text: bold, italic, underline, bullets, hyperlinks; plain-text fallback toggle.
     - Templates dropdown: user/system templates with variable preview (e.g., {Company}, {Role}).
     - AI suggestions: “Generate reply” button; presents 3 suggestions; user can insert/edit.
     - Attach files: drag & drop or “Attach” button; show file chips with size; remove individual files.
     - Send/Cancel buttons; disabled state until validations pass.
   - On Send: show progress; on success, new message appended to thread; toast “Sent”. On error, inline error with “Retry”.

5. Attachments
   - Message attachments: show file type icon, name, size, and actions (Preview where supported: PDF/images; otherwise Download).
   - Reply attachments: enforce size/count limits; show error per file with reason; support removing before send.

#### Acceptance criteria
- Emails tab appears on Job Details only when mailbox connected; otherwise shows connect prompt.
- Thread list groups only messages linked to the current job; unread badges clear upon view.
- “Refresh” triggers visible syncing state and updates “Last synced”.
- Unlinked messages can be searched and linked to a job; linked threads display the associated job meta.
- Composer:
  - Prefills recipient(s) and subject; blocks send if body empty.
  - Templates insert content at caret position; variables resolve using job/application context; unresolved variables are highlighted for user edit.
  - AI suggestions return up to 3 options; user can insert one; failure shows non-blocking error.
  - Attachments enforce max 25 MB total and max 20 files; oversize files are rejected with clear messaging.
- Sent replies appear in thread within 5 seconds with pending state that resolves to sent or error.
- Attachment previews work for PNG/JPG/PDF; others offer download only.
- All actions accessible via keyboard; focus order logical; buttons have ARIA labels; contrasts meet WCAG AA.

#### Out of scope
- Multiple email accounts, shared mailboxes, or Gmail integration.
- Composing net-new emails not tied to an existing thread.
- Advanced email features: scheduling, signatures management, read receipts, S/MIME, forwarding.
- Bulk operations across threads, tagging/labels, or smart folders.
- Admin delegation and team visibility.
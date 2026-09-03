# Backend PRD: Email Ingestion & Reply
**Feature:** Email Ingestion & Reply  
**Type:** backend

# Email Ingestion & Reply

## Feature overview
Enable AJAS to ingest relevant Microsoft 365 emails for tracked job opportunities and allow users to reply from within the app. The system links messages to JobPosting/Application records, manages attachments, and provides template-based and AI-assisted reply suggestions. All interactions respect user mailbox permissions and persist complete conversation context.

## Scope & behavior
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

## User-facing flows
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

## Acceptance criteria
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

## Out of scope
- Gmail/IMAP integration, calendar scheduling, contact management.
- UI for template management beyond simple IDs/variables.
- Full antivirus/malware scanning of attachments.
- Shared mailboxes and delegated send-on-behalf scenarios.
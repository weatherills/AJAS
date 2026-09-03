# Backend PRD: Review & Decision UI
**Feature:** Review & Decision UI  
**Type:** backend

# Review & Decision UI — Backend PRD

## Feature overview
Provide backend APIs to support reviewing AI-generated job–resume matches and saved jobs, viewing match details (summary, score, rationale), and making approve/reject decisions with optional comments. Persist decisions and full audit history for traceability and learning. Enable efficient queue views and detail retrieval with strict user scoping and idempotent decisioning.

## Scope & behavior
- Entities
  - Match: {matchId, userId, jobId, resumeId, score, summary, why, status: pending|approved|rejected, suggestion: approve|reject|none, createdAt, updatedAt, etag}
  - Decision: {decisionId, matchId, userId, decision: approve|reject, comment, createdAt, source: manual|system, version}
  - Audit Event: {eventId, entityType, entityId, userId, action, before, after, ts, ip}
  - Saved Job Queue Item: {queueItemId, userId, jobId, status: awaiting_decision|decided, createdAt}
- Data stores
  - Cosmos DB (serverless): collections for Matches, Decisions, SavedQueue, Audit (logical partition by userId; secondary partition/unique index on matchId).
  - Blob Storage: job/resume artifacts (read-only URIs), optional cached AI rationale blobs.
  - Storage Queue: “decision-events” for downstream learning/notifications.
- Permissions
  - Auth required (Bearer JWT). Only resource owner (userId from token) can read/act.
  - Scopes: read:review, write:review. 403 on missing scopes; 404 on cross-tenant/resource.
- Validations
  - decision ∈ {approve, reject}; comment ≤ 2000 chars; idempotency key required for POSTs making state changes.
  - ETag required for conditional updates (If-Match). 412 on mismatch.
- Concurrency/Idempotency
  - Idempotency-Key header deduplicates within 24h per userId+matchId+decision; respond with original result on duplicate.
  - Once decided, subsequent conflicting decisions return 409 unless overwrite=true and within 24h; overwrites create new Decision version and audit.
- Performance
  - List endpoints paginated: pageSize 10–100, default 25; continuation token for Cosmos.
  - P95 < 400ms for cache hits; AI detail enrichment falls back to stale cached data if AI > 2s.
- Errors
  - Standardized: 400 validation, 401/403 auth, 404 not found, 409 conflict, 412 precondition failed, 429 throttled, 500 server.

## User-facing flows
- Match Queue (pending)
  - GET /v1/matches?status=pending&minScore=&jobTitle=&createdAfter=&pageSize=&continuation=
  - Returns lightweight rows: matchId, job meta, resume meta, score, suggestion, createdAt.
- Queue View (saved jobs awaiting decision)
  - GET /v1/queue/saved-jobs?status=awaiting_decision&...
- Detail Pane
  - GET /v1/matches/{matchId}
  - Returns full summary, score, why (explanations), AI suggestion, links to blobs (SAS URIs, short-lived ≤10 min), and current decision if exists.
  - If rationale missing, backend triggers async enrich (Container App calling AI Matching Service/Azure OpenAI). Response should not block >2s; serve stale cache if available.
- Approve/Reject + Comments
  - POST /v1/matches/{matchId}/decision with {decision, comment?, overwrite?}
  - Validates ownership, state, idempotency, ETag from match. Persists Decision, updates Match.status, writes Audit, enqueues event.
- History & Audit
  - GET /v1/decisions/history?matchId= or jobId= or resumeId=
  - Returns chronological decision trail, including overwrites and system-generated suggestions (read-only).

## API contracts
- GET /v1/matches
  - Query: status [pending|approved|rejected], minScore [0–100], jobTitle (substring), createdAfter (ISO8601), pageSize, continuation
  - 200: {items: [...], continuationToken?}
- GET /v1/matches/{matchId}
  - 200: {match, decision?, blobs: {jobUrl, resumeUrl}}
- POST /v1/matches/{matchId}/decision
  - Headers: Idempotency-Key, If-Match (match.etag)
  - Body: {decision: "approve"|"reject", comment?: string, overwrite?: boolean}
  - 200/201: {decisionId, matchStatus, version, occurredAt}
  - 409 if already decided and overwrite not allowed
- GET /v1/queue/saved-jobs
  - 200: {items: [{queueItemId, jobId, jobTitle, createdAt}], continuationToken?}
- GET /v1/decisions/history
  - Query: matchId | jobId | resumeId (exactly one)
  - 200: {items: [{decisionId, decision, comment, source, version, createdAt, actor}]}

## Security
- JWT validation; userId from token becomes Cosmos partition key. Enforce per-request access to entities by userId.
- SAS URLs for blobs scoped to read-only, 10-minute expiry; never store SAS in DB.
- Input sanitized and length-limited; comments logged only in DB, not in queues.
- Audit includes actor, ip (from X-Forwarded-For), before/after snapshots (diff of Match.status and Decision).

## Background processing
- On decision created/updated:
  - Enqueue to storage queue: {eventType:"DecisionCreated", userId, matchId, decisionId, timestamp}
  - Downstream consumers may retrain or notify; retries with poison queue after 5 attempts.

## Acceptance criteria
- Listing pending matches returns only caller’s items with correct pagination and filtering.
- Detail endpoint returns summary, score, why, suggestion; serves cached rationale if AI unavailable; no call exceeds 2s for first byte.
- Decisions are idempotent by Idempotency-Key; duplicate submissions return same decisionId.
- Conditional update with If-Match prevents lost updates; stale ETag yields 412.
- Once a decision is made, conflicting updates return 409 unless overwrite=true within 24h; both actions appear in history with incremented versions.
- Audit entries created for every decision change; entries immutable and queryable by matchId.
- Blob SAS URLs are time-bound and not stored; access outside window is denied.
- All endpoints require auth and enforce user scoping; unauthorized returns 401/403; cross-user access returns 404.

## Out of scope
- Resume parsing, job ingestion, and AI scoring generation.
- Notification delivery, ML retraining logic, or analytics dashboards.
- Team/shared reviews or multi-user workflows.
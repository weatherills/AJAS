# Review & Decision UI — Product Requirements

> **Runbook phase:** Phase 1 &nbsp;·&nbsp; **Feature key:** `review-decision-ui`
>
> Consolidated PRD for the "Review & Decision UI" feature — combines the backend,
> database, and frontend requirements in one place. The canonical,
> CodeSpring-generated sources remain the source of truth:
> - [Backend PRD](../../.codespring/PRDs/review-decision-ui/backend-prd-review-decision-ui.md)
> - [Database PRD](../../.codespring/PRDs/review-decision-ui/database-prd-review-decision-ui.md)
> - [Frontend PRD](../../.codespring/PRDs/review-decision-ui/frontend-prd-review-decision-ui.md)

---

## Backend

### Backend PRD: Review & Decision UI
**Feature:** Review & Decision UI  
**Type:** backend

### Review & Decision UI — Backend PRD

#### Feature overview
Provide backend APIs to support reviewing AI-generated job–resume matches and saved jobs, viewing match details (summary, score, rationale), and making approve/reject decisions with optional comments. Persist decisions and full audit history for traceability and learning. Enable efficient queue views and detail retrieval with strict user scoping and idempotent decisioning.

#### Scope & behavior
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

#### User-facing flows
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

#### API contracts
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

#### Security
- JWT validation; userId from token becomes Cosmos partition key. Enforce per-request access to entities by userId.
- SAS URLs for blobs scoped to read-only, 10-minute expiry; never store SAS in DB.
- Input sanitized and length-limited; comments logged only in DB, not in queues.
- Audit includes actor, ip (from X-Forwarded-For), before/after snapshots (diff of Match.status and Decision).

#### Background processing
- On decision created/updated:
  - Enqueue to storage queue: {eventType:"DecisionCreated", userId, matchId, decisionId, timestamp}
  - Downstream consumers may retrain or notify; retries with poison queue after 5 attempts.

#### Acceptance criteria
- Listing pending matches returns only caller’s items with correct pagination and filtering.
- Detail endpoint returns summary, score, why, suggestion; serves cached rationale if AI unavailable; no call exceeds 2s for first byte.
- Decisions are idempotent by Idempotency-Key; duplicate submissions return same decisionId.
- Conditional update with If-Match prevents lost updates; stale ETag yields 412.
- Once a decision is made, conflicting updates return 409 unless overwrite=true within 24h; both actions appear in history with incremented versions.
- Audit entries created for every decision change; entries immutable and queryable by matchId.
- Blob SAS URLs are time-bound and not stored; access outside window is denied.
- All endpoints require auth and enforce user scoping; unauthorized returns 401/403; cross-user access returns 404.

#### Out of scope
- Resume parsing, job ingestion, and AI scoring generation.
- Notification delivery, ML retraining logic, or analytics dashboards.
- Team/shared reviews or multi-user workflows.
---

## Database

### Database PRD: Review & Decision UI
**Feature:** Review & Decision UI  
**Type:** database

#### Feature Summary
Database support for a Review & Decision UI where a job seeker reviews AI-generated job–resume matches, sees summaries and suggestions, filters a queue, and records approve/reject decisions with comments. Includes traceable history and audit events.

#### Entities & Relationships
- matches: One record per job–resume pairing for a given user. Holds queue status, AI score/suggestion, explainability artifacts (summary/highlights), and denormalized job/resume fields for efficient filtering.
- decision_events: Immutable log of each approve/reject action (including edits/overrides). matches.latest_decision_id points to the most recent decision for quick reads.
- audit_events: Append-only telemetry for list/detail views, filter usage, and decision interactions to enable history and learning.

Relationships:
- matches (1) — (N) decision_events
- matches (0..1) — (1) latest_decision_id (FK to decision_events)
- matches (0..N) — (N) audit_events (by match_id)

#### Scope Mapping to Sub-features
- Match Queue / Queue View: Query matches by user_id partition, status=PENDING, with filterable fields (job_title, company, location, ai_score range, created time). Concurrency aided by optional lock fields for item claiming.
- Detail Pane / Details + Summary: Read a single match with AI score, suggestion, explanation (why), summary blob reference, and highlights JSON for display.
- Approve/Reject + Comments: Insert decision_events row; update matches.status, matches.latest_decision_id, matches.decided_at atomically. Comment is stored with the decision.
- History & Audit: decision_events provides decision history; audit_events captures non-decision interactions (views, filters, suggestion viewed) with payloads for reproducibility.

#### Constraints & Business Rules
- A match belongs to exactly one user (partition = user_id). Users cannot see or mutate others’ matches.
- status values: PENDING, APPROVED, REJECTED. Only one terminal status at a time; latest_decision_id must correspond to status.
- Decisions are append-only; superseded decisions remain for history via supersedes_decision_id.
- Optional optimistic locking via lock_owner and lock_expires_at prevents duplicate handling in queue UIs.
- AI fields are snapshots at match creation; decision_events also capture AI snapshot at decision time for auditability.

#### Indexing & Partitioning (Cosmos DB-aligned)
- Partition key: user_id on all tables to co-locate a user’s queue, decisions, and audits.
- matches indexes: status, queued_at, ai_score, job_title/company/location (for filters), decided_at, latest_decision_id.
- decision_events indexes: match_id, decided_at.
- audit_events indexes: match_id, event_type, occurred_at.

#### Edge Cases
- Re-decision: Inserting a new decision_event flips matches.status and latest_decision_id; previous decision is not deleted and is referenced via supersedes_decision_id.
- Lock expiry: If lock_expires_at < now, item is considered unlocked for queue claiming; audit UNLOCK_EXPIRED can be recorded.
- Missing artifacts: If summary_blob_uri or highlights_json is null, UI falls back to basic fields; record audit event for degraded view.

---

## Frontend

### Frontend PRD: Review & Decision UI
**Feature:** Review & Decision UI  
**Type:** frontend

### Review & Decision UI

#### Feature overview
Enables job seekers to quickly review AI-matched or saved job postings, view concise summaries and rationale, and make approve/reject decisions with optional comments. Optimizes throughput via a list + detail pane workflow, AI suggestions, filters, and a lightweight audit trail for learning and traceability.

#### Scope & behavior
- Views
  - Match Queue: AI-suggested matches awaiting decision.
  - Saved Queue: User-saved jobs awaiting decision.
  - History & Audit: Read-only list of prior decisions with notes.
  - Toggle via top-level segmented control: Matches | Saved | History.
- List (Match Queue and Saved Queue)
  - Columns: Job Title, Company, Location, Source (AI/Saved), Score (0–100), Applied? (Y/N), Added Date.
  - Filters: Score range slider, Company (typeahead), Location, Source (AI/Saved), Date added, Status (Awaiting/Approved/Rejected).
  - Sort: Score (desc default), Date added, Company, Title.
  - Pagination/infinite scroll (page size 25), total count, empty states with guidance.
  - Selection: Single-select highlights row and opens Detail Pane on the right.
- Detail Pane (sticky/right-side)
  - Header: Title, Company, Location, Link to original posting (opens new tab), Score badge, Status chip.
  - Summary: 3–5 bullet highlights from job and resume match; “Why it matches” explanation from AI Matching Service; show last refreshed timestamp.
  - AI Suggestion: “Recommend Approve/Reject/Review” with confidence; show rationale (max 400 chars); fallback to “No suggestion available” if missing.
  - Resume Highlights: Top skills matched/missing; years experience alignment; keywords. If resume not available, show “Resume not found” state.
  - Approve/Reject controls: Two primary buttons; inline comment input (up to 1,000 chars) with placeholder (“Add notes for your future self (optional)”).
  - Decision persistence: On click, disable buttons, show spinner; on success, update Status chip, remove from queue list, show toast. On failure, re-enable, show error toast with retry.
  - Keyboard shortcuts: A = Approve, R = Reject, Cmd/Ctrl+Enter = Save decision with comment focused.
- History & Audit
  - List columns: Job Title, Company, Decision (Approved/Rejected), Comment (truncated), Decided Date/Time, Source (AI/Saved), Score at decision.
  - Row click opens read-only Detail Pane with the state at decision time (as stored); if historical snapshot missing, show current data with “Snapshot unavailable” note.
  - Reconsider action: “Reopen” button moves the item back to the appropriate queue as Awaiting Decision; original audit entry remains immutable, and a new history entry will be created on new decision.
- Validations & errors
  - Comments optional for both approve/reject; trim whitespace; block >1,000 chars with counter and error.
  - Network/API errors: inline error in pane + toast; no data loss in comment field.
  - Permissions: Single-user scope (MVP). Only the signed-in user can view/edit their own queues and history.
- Accessibility & responsiveness
  - Fully keyboard navigable (tab order: list → pane → actions), visible focus states, ARIA roles for list, pane, and status updates.
  - Contrast-compliant badges and buttons.
  - Responsive: ≥1024px shows list + pane; <1024px shows list, tapping a row navigates to full-screen detail with top-back control. Decision buttons sticky at bottom on mobile.

#### User-facing flows
1. Review a match
   - Open Matches → filter by Score >70 → select row → read Summary/Suggestion → add optional comment → Approve or Reject → toast “Decision saved” → next row auto-selected (or pane closes on mobile).
2. Review saved job
   - Open Saved → select row → decide → item removed from Saved queue on success.
3. Failure state
   - Click Approve → network error → buttons re-enabled, error toast “Could not save decision. Try again.” → user retries without losing comment.
4. View history and reconsider
   - Open History → inspect decision details → click Reopen → item appears in Matches or Saved (based on original source) with status Awaiting.

#### Acceptance criteria
- Lists render with defined columns, filters, sort, pagination; empty states show actionable guidance.
- Selecting a row opens Detail Pane with summary, score, suggestion, and resume highlights (with appropriate fallbacks).
- Approve/Reject actions persist status and comment; UI disables during save; on success, item leaves queue and toast confirms.
- Comment input enforces 0–1,000 characters, shows remaining count and validation errors.
- Keyboard shortcuts A/R/Cmd+Enter function and are discoverable via tooltip or help hint.
- History displays immutable past decisions with timestamp, comment, score; missing snapshots show clear notice.
- Reopen moves item to Awaiting and retains original history entry.
- All views function on desktop and mobile per responsive rules; decision buttons remain reachable.
- Accessibility: focus management after decision, ARIA live region announces status updates, minimum contrast 4.5:1.

#### Out of scope
- Editing or deleting past decisions or comments.
- Bulk approve/reject.
- Metrics dashboards, exports, or notifications.
- Resume editing or job scraping within this UI.
- Multi-user collaboration or role-based permissions.
# Database PRD: Review & Decision UI
**Feature:** Review & Decision UI  
**Type:** database

## Feature Summary
Database support for a Review & Decision UI where a job seeker reviews AI-generated job–resume matches, sees summaries and suggestions, filters a queue, and records approve/reject decisions with comments. Includes traceable history and audit events.

## Entities & Relationships
- matches: One record per job–resume pairing for a given user. Holds queue status, AI score/suggestion, explainability artifacts (summary/highlights), and denormalized job/resume fields for efficient filtering.
- decision_events: Immutable log of each approve/reject action (including edits/overrides). matches.latest_decision_id points to the most recent decision for quick reads.
- audit_events: Append-only telemetry for list/detail views, filter usage, and decision interactions to enable history and learning.

Relationships:
- matches (1) — (N) decision_events
- matches (0..1) — (1) latest_decision_id (FK to decision_events)
- matches (0..N) — (N) audit_events (by match_id)

## Scope Mapping to Sub-features
- Match Queue / Queue View: Query matches by user_id partition, status=PENDING, with filterable fields (job_title, company, location, ai_score range, created time). Concurrency aided by optional lock fields for item claiming.
- Detail Pane / Details + Summary: Read a single match with AI score, suggestion, explanation (why), summary blob reference, and highlights JSON for display.
- Approve/Reject + Comments: Insert decision_events row; update matches.status, matches.latest_decision_id, matches.decided_at atomically. Comment is stored with the decision.
- History & Audit: decision_events provides decision history; audit_events captures non-decision interactions (views, filters, suggestion viewed) with payloads for reproducibility.

## Constraints & Business Rules
- A match belongs to exactly one user (partition = user_id). Users cannot see or mutate others’ matches.
- status values: PENDING, APPROVED, REJECTED. Only one terminal status at a time; latest_decision_id must correspond to status.
- Decisions are append-only; superseded decisions remain for history via supersedes_decision_id.
- Optional optimistic locking via lock_owner and lock_expires_at prevents duplicate handling in queue UIs.
- AI fields are snapshots at match creation; decision_events also capture AI snapshot at decision time for auditability.

## Indexing & Partitioning (Cosmos DB-aligned)
- Partition key: user_id on all tables to co-locate a user’s queue, decisions, and audits.
- matches indexes: status, queued_at, ai_score, job_title/company/location (for filters), decided_at, latest_decision_id.
- decision_events indexes: match_id, decided_at.
- audit_events indexes: match_id, event_type, occurred_at.

## Edge Cases
- Re-decision: Inserting a new decision_event flips matches.status and latest_decision_id; previous decision is not deleted and is referenced via supersedes_decision_id.
- Lock expiry: If lock_expires_at < now, item is considered unlocked for queue claiming; audit UNLOCK_EXPIRED can be recorded.
- Missing artifacts: If summary_blob_uri or highlights_json is null, UI falls back to basic fields; record audit event for degraded view.

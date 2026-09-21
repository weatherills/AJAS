# PRD: LinkedIn Easy Apply — Backend

Status: Placeholder committed to repo
PRD ID (AJAS): 7b3b3357-bfb8-406f-b3ed-4f7fbc9e152e
Feature: LinkedIn Easy Apply
Type: Backend

Overview
- Automate Easy Apply submissions with safe throttling, field mapping, resume/QA selection, and receipts.

Scope (MVP)
- Detect Easy Apply availability
- Map candidate data and dynamic questions
- Submit with rate limits and retries
- Capture confirmation artifacts (text/screenshot/ID)
- Full audit logging

Data Model (summary)
- ApplicationAttempt(id, jobPostingId, userId, resumeId, status, startedAt, finishedAt)
- ApplyReceipt(id, applicationAttemptId, provider, artifactType, url/hash)
- AuditEvent(id, applicationAttemptId, action, result, metadata)

Flows (high level)
1) Prepare context → 2) Fill form → 3) Validate → 4) Submit → 5) Capture receipt → 6) Persist + audit.

Non‑functional
- Idempotency per (user, job, resume)
- Backoff on blocks/captchas; fail closed to needs_manual

Acceptance (MVP)
- 5 sample jobs submit successfully with receipts recorded
- All attempts have an audit trail

Note
- The full PRD content lives in AJAS and is linked by the PRD ID above. This file tracks the repo copy and key pointers.

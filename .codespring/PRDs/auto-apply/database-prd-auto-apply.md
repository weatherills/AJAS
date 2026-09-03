# Database PRD: Auto-Apply
**Feature:** Auto-Apply  
**Type:** database

## Feature Summary
Schema to support Auto-Apply: creation/approval of attempts, package assembly (resume variant + optional AI cover letter + deep link), form autofill, API submission to Greenhouse/Lever, and end-to-end status tracking (including webhooks).

## Entities & Relationships
- auto_apply_attempts is the root per user+job attempt. All operational records (package, autofill values, submit requests, status events, webhooks) link to it via auto_apply_id.
- apply_packages captures the frozen artifacts used at submission time (resume variant, cover letter, filled form snapshot, deep link). Locked packages are immutable once queued/submitted.
- resume_variants stores personalized resume files for reuse across attempts; referenced by apply_packages.
- cover_letters stores uploaded or AI-generated cover letters; referenced by apply_packages.
- form_autofill_values holds resolved field values per attempt and vendor, derived from vendor_field_mappings and user/resume/profile data.
- vendor_field_mappings defines normalized-to-vendor field maps used by Form Autofill for Greenhouse/Lever.
- submit_requests tracks each API call to vendor submit endpoints, request/response payload URIs, retries, rate limits, and vendor-issued IDs.
- status_events is the append-only audit trail for lifecycle and vendor updates.
- webhook_callbacks ingests vendor callbacks (e.g., application created/state changes) and links them back to attempts when possible.

## Key Behaviors & Constraints
- Attempt lifecycle (auto_apply_attempts.status): draft → queued → submitting → submitted → succeeded | failed | needs_review | rate_limited.
- Approval gate: approved=true with approved_ts is required before status can transition to queued or beyond.
- Idempotency: submit_requests.idempotency_key must be unique per vendor to prevent duplicate submissions on retries.
- Package immutability: apply_packages.locked=true prohibits changes to resume_variant_id, cover_letter_id, filled_fields_json, deep_link_url.
- Form Autofill: A complete apply requires required=true fields in form_autofill_values to be present with non-empty value; confidence stored for review.
- Vendor linkage: submit_requests.vendor_application_id and webhook_callbacks.vendor_application_id are used to correlate vendor status; enforce uniqueness per vendor.
- Error handling: last_error_code/message on auto_apply_attempts is updated from terminal submit_requests failures.

## Partitioning & Indexing (Cosmos DB guidance)
- Partition keys: user_id for resume_variants; auto_apply_id for apply_packages, form_autofill_values, submit_requests, status_events; vendor for vendor_field_mappings; vendor_application_id for webhook_callbacks (or hash thereof if needed).
- Suggested indices:
  - auto_apply_attempts: (user_id, status), (vendor, source_application_id)
  - submit_requests: (auto_apply_id, status), (vendor, vendor_request_id), (vendor, vendor_application_id), (idempotency_key)
  - webhook_callbacks: (vendor, vendor_application_id), (dedupe_key)
  - form_autofill_values: (auto_apply_id, vendor, field_key)
  - status_events: (auto_apply_id, created_ts DESC)

## Data Retention
- Payload/artefact bodies stored in Blob Storage (URIs referenced here). Retain status_events and submit_requests for 18 months; webhook payloads for 90 days.

## Enumerations (stored as TEXT)
- vendor: greenhouse | lever | manual
- mode: api | manual_package
- status (attempt): draft | queued | submitting | submitted | succeeded | failed | needs_review | rate_limited
- submit_requests.status: queued | sent | retrying | succeeded | failed
- cover_letters.source: ai | upload | none
- form_autofill_values.source: resume | profile | user_input | ai_inferred
- status_events.event_type: created | approved | queued | package_built | submission_started | submission_succeeded | submission_failed | vendor_ack | vendor_rejected | needs_review | rate_limited
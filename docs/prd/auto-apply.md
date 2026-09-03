# Auto-Apply — Product Requirements

> **Runbook phase:** Phase 2 &nbsp;·&nbsp; **Feature key:** `auto-apply`
>
> Consolidated PRD for the "Auto-Apply" feature — combines the backend,
> database, and frontend requirements in one place. The canonical,
> CodeSpring-generated sources remain the source of truth:
> - [Backend PRD](../../.codespring/PRDs/auto-apply/backend-prd-auto-apply.md)
> - [Database PRD](../../.codespring/PRDs/auto-apply/database-prd-auto-apply.md)
> - [Frontend PRD](../../.codespring/PRDs/auto-apply/frontend-prd-auto-apply.md)

---

## Backend

### Backend PRD: Auto-Apply
**Feature:** Auto-Apply  
**Type:** backend

### Auto-Apply

#### Feature overview
Enable approved users to programmatically apply to job postings via supported source APIs (Greenhouse, Lever). When programmatic submission is not possible, generate a manual application package (resume variant, optional cover letter, deep link). Persist end-to-end status, artifacts, and provider responses for traceability and user feedback.

#### Scope & behavior
- Supported sources:
  - Greenhouse Submit — programmatic apply where the posting and partner API supports it.
  - Lever Submit — programmatic apply where supported.
  - Manual Package — fallback when programmatic submit is unavailable or blocked (e.g., captcha, SSO wall).
- Form Autofill — map normalized resume/profile fields to provider application fields; validate formats and required fields pre-submit.
- Cover Letter Generation (optional) — Azure OpenAI based; store generated artifact; allow “none”, “upload”, or “generate”.
- Status Tracking — persist application request, state transitions, external IDs, errors, and artifacts.

States
- created → queued → preparing (artifacts, mappings) → submitting (provider) → submitted
- needs_manual (fallback path) → packaged
- rejected (pre-submit validation) | failed (runtime/provider error) | cancelled
- Terminal: submitted, packaged, failed, cancelled

Validations
- Required: user_id, job_source (greenhouse|lever|manual), job_posting_id or posting_url, resume_id or resume_blob_ref, consent_approved=true.
- Attachments: PDF/DOCX up to 5 MB; virus scan pass; text extractable.
- Autofill: email valid, phone E.164, location ISO country/state where required, work history dates coherent, required custom questions present if fetched.
- Idempotency: reject duplicate in-flight requests for same user_id + job_posting_id + resume_hash.

Permissions & security
- Auth: user JWT (AJAS identity) required for all endpoints; service-to-service auth for workers.
- Provider credentials/tokens (if needed) stored encrypted; use least-privilege per user/tenant.
- PII stored in Cosmos with field-level encryption; files in Blob with private containers and SAS on-demand.

Performance & reliability
- Queue-based orchestration; p95 end-to-end under 30s for programmatic applies (excluding provider latency).
- Exponential backoff retries (max 3) for transient provider/network errors; no retry on 4xx validation errors.
- Respect provider rate limits; introduce jitter and per-source throttles.
- Observability: structured logs with correlation_id; metrics for success/fail/fallback.

#### User-facing flows
1) Programmatic Apply (Greenhouse/Lever)
- Client POSTs apply request.
- Worker fetches posting metadata, maps fields, assembles attachments, optional cover letter (generate via Azure OpenAI <= 1,000 tokens; budget guard).
- Pre-submit validation; if fail → rejected.
- Submit via provider API; capture external_application_id, response codes.
- Update state to submitted with timestamp and artifacts.

2) Fallback to Manual Package
- Triggered when: provider unsupported, posting requires captcha/SSO, API returns unsupported schema, or hard 4xx.
- Generate package: selected resume variant, optional cover letter, and deep link (canonical posting URL).
- Store zip/pdf bundle in Blob; set state to packaged with reason.

3) Status Tracking
- Client polls GET by request_id; returns state, artifacts URIs (SAS-scoped), external IDs, errors.
- If provider webhooks available, ingest to update state; else minimal polling (<= 2 attempts) to confirm acceptance when API supports.

Edge cases
- Duplicate apply attempt → 409 with existing request_id.
- Closed/invalid posting → rejected with provider_reason.
- File type/size violation → rejected.
- Cover letter generation failure → proceed without cover letter and log warning, not fail submit.
- User cancellation allowed only before submitting.

#### API endpoints
- POST /v1/auto-apply/requests
  - Auth: Bearer user
  - Body: {
      job_source: "greenhouse"|"lever"|"manual",
      job_posting_id?: string,
      posting_url?: string,
      resume_id?: string,
      resume_blob_ref?: string,
      cover_letter_mode: "none"|"upload"|"generate",
      cover_letter_blob_ref?: string,
      autofill: boolean,
      answers?: { [question_key]: string },
      idempotency_key?: string
    }
  - 201: { request_id, state, created_at }
  - 400/401/409 as applicable

- GET /v1/auto-apply/requests/{request_id}
  - 200: {
      request_id, state, state_history[],
      source: { type, job_posting_id, posting_url, external_application_id? },
      artifacts: { resume_blob_sas, cover_letter_blob_sas?, package_blob_sas? },
      validation_errors?, failure_reason?, submitted_at?, packaged_at?
    }

- POST /v1/auto-apply/requests/{request_id}/cancel
  - 202: { state: "cancelled" } if not yet submitting
  - 409 if already terminal or submitting

- Webhook (optional, per provider): POST /v1/auto-apply/webhooks/{provider}
  - Auth: provider secret
  - Body: provider-specific; map to request_id/external_application_id; update state/metadata.

#### Data & storage
- Cosmos DB collections:
  - application_requests: core entity, states, mappings, provider metadata, user_id, idempotency_key.
  - provider_submissions: external ids, payload snapshots, responses.
- Blob Storage:
  - resumes/, cover_letters/, packages/, provider_payloads/; all private.
- Queues:
  - auto-apply-requests (ingress), auto-apply-submits, auto-apply-webhooks.

#### Acceptance criteria
- Creating an Auto-Apply request validates inputs, enforces idempotency, and enqueues work.
- For supported Greenhouse/Lever postings, system submits via API and records external_application_id; final state = submitted.
- When programmatic submit is not possible, system produces a downloadable package with deep link; final state = packaged with reason.
- Autofill maps standard resume fields to provider fields with documented transformations; missing required fields yield rejected with field-level errors.
- Optional cover letter:
  - generate: created via Azure OpenAI, stored, linked; generation failure does not block submission.
  - upload: validated and attached.
- Status endpoint reflects real-time state transitions; includes timestamps and artifacts with time-limited SAS URIs.
- Retries occur only on transient errors; no duplicate external submissions for same request (idempotency with external_application_id).
- Provider rate limits are respected; no 429s observed in steady-state test runs.
- Security: all PII encrypted at rest; endpoints require auth; provider webhooks verified by signature/secret.
- Metrics and logs available for request lifecycle, errors, fallback rate, and generation usage.

#### Out of scope
- UI/UX for account linking, consent collection, or notification delivery.
- Resume variant generation or editing beyond selection and storage reference.
- Ongoing post-submit tracking within employer ATS (beyond initial submission acknowledgment).
- Multi-ATS support beyond Greenhouse/Lever in this iteration.
---

## Database

### Database PRD: Auto-Apply
**Feature:** Auto-Apply  
**Type:** database

#### Feature Summary
Schema to support Auto-Apply: creation/approval of attempts, package assembly (resume variant + optional AI cover letter + deep link), form autofill, API submission to Greenhouse/Lever, and end-to-end status tracking (including webhooks).

#### Entities & Relationships
- auto_apply_attempts is the root per user+job attempt. All operational records (package, autofill values, submit requests, status events, webhooks) link to it via auto_apply_id.
- apply_packages captures the frozen artifacts used at submission time (resume variant, cover letter, filled form snapshot, deep link). Locked packages are immutable once queued/submitted.
- resume_variants stores personalized resume files for reuse across attempts; referenced by apply_packages.
- cover_letters stores uploaded or AI-generated cover letters; referenced by apply_packages.
- form_autofill_values holds resolved field values per attempt and vendor, derived from vendor_field_mappings and user/resume/profile data.
- vendor_field_mappings defines normalized-to-vendor field maps used by Form Autofill for Greenhouse/Lever.
- submit_requests tracks each API call to vendor submit endpoints, request/response payload URIs, retries, rate limits, and vendor-issued IDs.
- status_events is the append-only audit trail for lifecycle and vendor updates.
- webhook_callbacks ingests vendor callbacks (e.g., application created/state changes) and links them back to attempts when possible.

#### Key Behaviors & Constraints
- Attempt lifecycle (auto_apply_attempts.status): draft → queued → submitting → submitted → succeeded | failed | needs_review | rate_limited.
- Approval gate: approved=true with approved_ts is required before status can transition to queued or beyond.
- Idempotency: submit_requests.idempotency_key must be unique per vendor to prevent duplicate submissions on retries.
- Package immutability: apply_packages.locked=true prohibits changes to resume_variant_id, cover_letter_id, filled_fields_json, deep_link_url.
- Form Autofill: A complete apply requires required=true fields in form_autofill_values to be present with non-empty value; confidence stored for review.
- Vendor linkage: submit_requests.vendor_application_id and webhook_callbacks.vendor_application_id are used to correlate vendor status; enforce uniqueness per vendor.
- Error handling: last_error_code/message on auto_apply_attempts is updated from terminal submit_requests failures.

#### Partitioning & Indexing (Cosmos DB guidance)
- Partition keys: user_id for resume_variants; auto_apply_id for apply_packages, form_autofill_values, submit_requests, status_events; vendor for vendor_field_mappings; vendor_application_id for webhook_callbacks (or hash thereof if needed).
- Suggested indices:
  - auto_apply_attempts: (user_id, status), (vendor, source_application_id)
  - submit_requests: (auto_apply_id, status), (vendor, vendor_request_id), (vendor, vendor_application_id), (idempotency_key)
  - webhook_callbacks: (vendor, vendor_application_id), (dedupe_key)
  - form_autofill_values: (auto_apply_id, vendor, field_key)
  - status_events: (auto_apply_id, created_ts DESC)

#### Data Retention
- Payload/artefact bodies stored in Blob Storage (URIs referenced here). Retain status_events and submit_requests for 18 months; webhook payloads for 90 days.

#### Enumerations (stored as TEXT)
- vendor: greenhouse | lever | manual
- mode: api | manual_package
- status (attempt): draft | queued | submitting | submitted | succeeded | failed | needs_review | rate_limited
- submit_requests.status: queued | sent | retrying | succeeded | failed
- cover_letters.source: ai | upload | none
- form_autofill_values.source: resume | profile | user_input | ai_inferred
- status_events.event_type: created | approved | queued | package_built | submission_started | submission_succeeded | submission_failed | vendor_ack | vendor_rejected | needs_review | rate_limited
---

## Frontend

### Frontend PRD: Auto-Apply
**Feature:** Auto-Apply  
**Type:** frontend

### Auto-Apply

#### 1) Feature overview
Auto-Apply enables users to approve and submit job applications directly from AJAS. For supported sources (Greenhouse, Lever), the system auto-fills and programmatically submits; otherwise, it generates a manual application package. Users can review, customize (resume variant, optional AI cover letter), submit, and track status in one place.

#### 2) Scope & behavior
- Entry points
  - Job card/listing: “Auto-Apply” primary action if job is in-scope; otherwise disabled with tooltip explaining why.
  - Bulk mode: Select multiple eligible jobs and apply in sequence (MVP may be single-job only if bulk is deferred).
- Approvals & permissions
  - Requires completed profile (name, email, phone, location), at least one resume on file, and user consent to terms.
  - For programmatic submit, user must confirm final data and explicitly authorize submission per job.
- Greenhouse Submit (programmatic)
  - When job source = Greenhouse and endpoint supported, show “Programmatic submit available” badge.
  - Previews mapped fields and attached files (resume, optional cover letter).
  - On submit, UI transitions to Queued → Submitting → Submitted or Needs Action/Failed.
- Lever Submit (programmatic)
  - Same behavior as Greenhouse with Lever-specific field set; show badge accordingly.
- Manual Package (fallback)
  - When programmatic not supported or blocked (e.g., CAPTCHA, unsupported custom questions), provide:
    - Selected resume variant
    - Optional cover letter (generated or uploaded)
    - Deep link to source application page
    - Downloadable package (PDF bundle) and “Copy answers” if autofill values exist
- Form Autofill
  - Maps resume/profile fields (name, email, phone, location, links, experience, education) to source fields.
  - Shows a read-only preview for programmatic submit; editable fields for manual package.
  - Validations: required fields, max lengths (show counters), allowed file types/sizes. Inline errors block submit.
- Cover Letter Generation (optional)
  - Toggle “Generate cover letter.” Requires selected resume variant and job description text.
  - States: Idle → Generating → Ready (editable rich text) → Regenerate.
  - Token/usage limits surfaced as non-blocking warnings; user can proceed without a letter.
- Submit via API
  - Single job submit triggers async backend; front end shows real-time state with optimistic progress.
  - Errors categorized and surfaced: Rate limited (retry scheduled), Auth/Session required (Needs Action), Validation failed (Fix fields), Unknown error (Failed).
- Status Tracking
  - Application detail panel shows status: Draft, Queued, Submitting, Submitted, Needs Action, Failed.
  - If backend later confirms outcome, show: Received, Duplicate Detected, Rejected (auto), Interview Requested.
  - Each status includes timestamp and last event note. Provide “View Logs” for request ID and last error.
  - Users can cancel while Queued; disabled once Submitting.

Accessibility & responsiveness
- All actions keyboard-accessible, focus-managed modals, ARIA live regions for status updates, descriptive error text.
- Responsive layout: modal adapts to mobile (full-screen) with collapsible sections.

#### 3) User-facing flows
- Programmatic submit (Greenhouse/Lever)
  1) Click Auto-Apply → Review modal opens with source badge.
  2) Select resume variant; toggle/generate cover letter; review autofill preview.
  3) Check consent → Submit.
  4) See Queued → Submitting → Submitted (or Needs Action/Failed). Close or open Status panel.
- Manual package
  1) Click Auto-Apply → Fallback banner indicates manual package.
  2) Select resume; optional cover letter (generate/edit).
  3) Review/edit mapped answers; Download package and Open application link.
  4) Mark as “Manually Submitted” after user completes on source; status updates to Submitted (Manual).
- Edge cases
  - CAPTCHA or login wall detected → show Needs Action with guidance button (“Open site to complete”).
  - Unsupported custom questions → highlight fields and switch to Manual Package.
  - Duplicate application response → status updates to Duplicate Detected with note.
  - File upload failure → inline error; disable submit until resolved.

#### 4) Acceptance criteria
- Auto-Apply button appears only for jobs with sufficient metadata; disabled state shows reason tooltip.
- Review modal displays correct source badge (Greenhouse/Lever/manual) and mapped field preview.
- Resume variant selection is required; cover letter optional; generation shows progress and retry on failure.
- Submit button disabled until all required fields valid and consent checked.
- On submit, status transitions render without page reload and persist after refresh.
- Manual package provides working download and deep link; user can mark as manually submitted.
- Status list shows latest state, timestamp, and last note; filters by status work.
- Errors categorized and user messaging matches category; recovery actions visible where applicable.
- Fully keyboard navigable; screen reader announces status changes.

#### 5) Out of scope
- Creating external accounts or bypassing CAPTCHAs/auth walls.
- Editing raw JSON payloads or backend configuration.
- Interview scheduling, offer management, or employer communications.
- Guaranteeing acceptance by external systems beyond submission confirmation.
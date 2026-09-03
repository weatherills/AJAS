# Backend PRD: Auto-Apply
**Feature:** Auto-Apply  
**Type:** backend

# Auto-Apply

## Feature overview
Enable approved users to programmatically apply to job postings via supported source APIs (Greenhouse, Lever). When programmatic submission is not possible, generate a manual application package (resume variant, optional cover letter, deep link). Persist end-to-end status, artifacts, and provider responses for traceability and user feedback.

## Scope & behavior
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

## User-facing flows
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

## API endpoints
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

## Data & storage
- Cosmos DB collections:
  - application_requests: core entity, states, mappings, provider metadata, user_id, idempotency_key.
  - provider_submissions: external ids, payload snapshots, responses.
- Blob Storage:
  - resumes/, cover_letters/, packages/, provider_payloads/; all private.
- Queues:
  - auto-apply-requests (ingress), auto-apply-submits, auto-apply-webhooks.

## Acceptance criteria
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

## Out of scope
- UI/UX for account linking, consent collection, or notification delivery.
- Resume variant generation or editing beyond selection and storage reference.
- Ongoing post-submit tracking within employer ATS (beyond initial submission acknowledgment).
- Multi-ATS support beyond Greenhouse/Lever in this iteration.
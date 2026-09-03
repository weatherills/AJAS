# Frontend PRD: Auto-Apply
**Feature:** Auto-Apply  
**Type:** frontend

# Auto-Apply

## 1) Feature overview
Auto-Apply enables users to approve and submit job applications directly from AJAS. For supported sources (Greenhouse, Lever), the system auto-fills and programmatically submits; otherwise, it generates a manual application package. Users can review, customize (resume variant, optional AI cover letter), submit, and track status in one place.

## 2) Scope & behavior
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

## 3) User-facing flows
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

## 4) Acceptance criteria
- Auto-Apply button appears only for jobs with sufficient metadata; disabled state shows reason tooltip.
- Review modal displays correct source badge (Greenhouse/Lever/manual) and mapped field preview.
- Resume variant selection is required; cover letter optional; generation shows progress and retry on failure.
- Submit button disabled until all required fields valid and consent checked.
- On submit, status transitions render without page reload and persist after refresh.
- Manual package provides working download and deep link; user can mark as manually submitted.
- Status list shows latest state, timestamp, and last note; filters by status work.
- Errors categorized and user messaging matches category; recovery actions visible where applicable.
- Fully keyboard navigable; screen reader announces status changes.

## 5) Out of scope
- Creating external accounts or bypassing CAPTCHAs/auth walls.
- Editing raw JSON payloads or backend configuration.
- Interview scheduling, offer management, or employer communications.
- Guaranteeing acceptance by external systems beyond submission confirmation.
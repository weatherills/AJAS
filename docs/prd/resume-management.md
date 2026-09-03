# Resume Management — Product Requirements

> **Runbook phase:** Phase 4 &nbsp;·&nbsp; **Feature key:** `resume-management`
>
> Consolidated PRD for the "Resume Management" feature — combines the backend,
> database, and frontend requirements in one place. The canonical,
> CodeSpring-generated sources remain the source of truth:
> - [Backend PRD](../../.codespring/PRDs/resume-management/backend-prd-resume-management.md)
> - [Database PRD](../../.codespring/PRDs/resume-management/database-prd-resume-management.md)
> - [Frontend PRD](../../.codespring/PRDs/resume-management/frontend-prd-resume-management.md)

---

## Backend

### Backend PRD: Resume Management
**Feature:** Resume Management  
**Type:** backend

Feature overview
Resume Management enables users to upload resume files (PDF/DOCX), convert them into a normalized schema for downstream AI matching, correct parsing errors through field edits, select an active resume per application run, and manage a personal resume library. It ensures secure file storage, reliable async parsing, and validated structured data for consistent downstream consumption.

Scope & behavior
- File types and limits:
  - Accept: application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document
  - Max size: 10 MB; max pages: 20 (PDF) if detectable during parse
  - Reject password-protected/encrypted PDFs and corrupted DOCX
- States:
  - uploaded → parsing → parsed | parse_failed
  - deleted (soft-deleted; not selectable)
- Ownership/permissions:
  - All operations require authenticated user; access restricted to ownerUserId
  - A resume can only be set active for runs owned by the same user
- Storage:
  - Original file stored in Azure Blob Storage under user-scoped container/prefix
  - Metadata and parsed schema stored in Cosmos DB
- Parsing:
  - Asynchronous via Azure Storage Queue; worker in Azure Container Apps
  - Uses Azure OpenAI to extract fields into schema; retries up to 2 times on transient failures; exponential backoff
- Validation:
  - Dates ISO 8601 (YYYY-MM-DD or YYYY-MM)
  - endDate must be >= startDate or null for current
  - String max lengths: company/title/institution/degree/field 200; descriptions 2000; skills 100 per skill, max 200 skills
  - Arrays: experience <= 50, education <= 30, skills <= 200
  - Required in parsed/editable data: at least one of skills/experience/education must be non-empty
- Active resume per run:
  - Only one active resume per runId
  - Allowed statuses: parsed, parsing, uploaded, parse_failed (consumer must handle missing parsed fields); not allowed: deleted
  - Updating active resume overwrites previous selection
- Deletion:
  - Soft-delete: mark status=deleted, record deletedAt; revoke active selection on any runs; generate a deletion tombstone
  - Blob retained for 30 days; hard-delete out of scope

API endpoints
- POST /resumes
  - Multipart file upload (field: file)
  - 201 returns {id, status:"uploaded"}; enqueues parse job
  - Errors: 400, 413, 415
- GET /resumes?cursor&limit
  - Returns paginated list of {id, fileName, mimeType, size, status, createdAt, updatedAt, lastParseAt}
- GET /resumes/{id}
  - Returns metadata and parsed data {skills, experience, education}, status, lastParseError (if any)
- GET /resumes/{id}/preview-url
  - Returns short-lived SAS URL (read-only, 10-minute expiry) to original file; 404 if deleted
- PATCH /resumes/{id}
  - Body: {skills?, experience?, education?} Partial update with validation; sets status to parsed if previously parse_failed and data now valid
- DELETE /resumes/{id}
  - Soft-delete; 204; idempotent
- POST /runs/{runId}/active-resume
  - Body: {resumeId}; 200 returns {runId, resumeId, effectiveAt}
  - Validates ownership and status != deleted
- GET /runs/{runId}/active-resume
  - Returns current selection {runId, resumeId} or 404 if none

Data model (Cosmos DB)
- resumes
  - id (UUID), ownerUserId, fileName, mimeType, size, blobPath, status, createdAt, updatedAt, lastParseAt, lastParseError, fileHash (SHA256), parsed: {skills[], experience[], education[]}, parsedVersion (int), deletedAt?
- run_active_resume
  - id (UUID), runId, ownerUserId, resumeId, effectiveAt

Async parsing flow
1) POST /resumes stores blob + creates resume doc with status=uploaded
2) Enqueue message: {resumeId, ownerUserId, blobPath}
3) Worker sets status=parsing; extracts text; calls Azure OpenAI; normalizes to schema; validates; updates resume doc, status=parsed
4) On failure: retry up to 2; then status=parse_failed with lastParseError

Security
- Auth via platform standard (AAD token) required on all endpoints
- Enforce ownerUserId match on every operation
- SAS URLs scoped to single blob, read-only, 10m expiry
- PII encrypted at rest (Blob, Cosmos); no data logged beyond hashes/IDs; redact OpenAI prompts/responses in logs

Performance & limits
- P95 upload: <3s for 5 MB
- P95 parse completion: <60s; client should poll GET /resumes/{id} every 3–5s
- Rate limit: 30 uploads/user/hour; 5 concurrent parses/user

User-facing flows
- Upload: user uploads file → 201 returned → status progresses to parsed or parse_failed → UI polls for status
- Edit: user fetches parsed data → PATCH with corrections → validation errors returned 400 with field paths
- Set active: user posts resumeId for a runId → returns selection; updating replaces prior
- Library: user lists resumes, requests preview URL to render/download, and can soft-delete

Acceptance criteria
- Uploading valid PDF/DOCX creates a resume, stores blob, and enqueues parse job
- Unsupported type, oversize, or encrypted files are rejected with correct HTTP status
- Parsing populates schema and sets status=parsed; failures set parse_failed with human-readable error
- PATCH enforces validation rules and returns 400 with JSON pointer paths on violations
- Active resume selection only allows owner’s non-deleted resumes and is one-per-run
- Deleting a resume revokes any active selection for that run and hides resume from listings
- Preview URLs are time-limited and inaccessible post-expiry
- Users cannot access or mutate others’ resumes or selections

Out of scope
- Hard-delete and legal retention workflows
- Resume authoring/generation
- Multi-user sharing or team permissions
- Versioning across multiple edited states (single current parsed state only)
- Importing from external drives via Microsoft Graph (future)
---

## Database

### Database PRD: Resume Management
**Feature:** Resume Management  
**Type:** database

#### Feature Summary
Database schema for Resume Management in AJAS: store uploaded resume files, parse into structured entities (skills, experience, education), allow edits with validation metadata, manage library state (list/preview/delete), and select an active resume per application run.

#### Entities & Relationships
- resumes (parent) — one record per uploaded resume version per user; stores file metadata, processing state, validation flags, and preview.
- resume_contacts — optional 1:1 contact/profile info for a resume.
- resume_skills — 1:N skills linked to a resume.
- resume_experiences — 1:N work history entries linked to a resume.
- resume_educations — 1:N education entries linked to a resume.
- run_resume_selections — maps a run to the chosen resume (exactly one per run). Prevents use of deleted resumes.
- resume_parse_events — append-only log of ingestion/parsing/edit events for observability.

#### Core Behaviors
- Upload Resume
  - Accept PDF/DOCX; create resumes row with processing_status='uploaded', store blob_uri, checksum, mime_type, file_size, and original_filename.
  - Enqueue parsing externally; when queued/started/succeeded/failed, append resume_parse_events and update processing_status and parsed_at / parsing_error.
  - Soft-delete via is_deleted=true and deleted_at; preserve original file/structured data for audit.
- Parse to Schema
  - On success, create/update child rows (contacts/skills/experiences/educations) with source='parsed' and set parsing_confidence (0–100).
  - Maintain order_index for deterministic UI ordering.
- Edit & Validate
  - Edits write to child tables with source='manual'; update resumes.validated and validated_at when all required fields pass client/server validation.
  - last_edited_by and updated_at reflect latest change on parent; child rows carry updated_at.
- Set Active Resume (per run)
  - Insert run_resume_selections with unique(run_id) ensuring only one active resume per run.
  - Enforce referential integrity: run_resume_selections.user_id must match resumes.user_id; reject if resumes.is_deleted=true or processing_status!='parsed'.
- Library Management
  - List resumes per user ordered by updated_at desc; exclude is_deleted unless explicitly requested.
  - Preview from preview_blob_uri or text_preview; never expose blob_uri for deleted resumes.
  - Delete: mark is_deleted, set deleted_at; cascade not required, but selection for future runs must be blocked.

#### Constraints & Validation
- resumes.user_id required.
- processing_status in {uploaded, queued, parsing, parsed, failed}.
- File constraints: mime_type in {application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document}; file_size > 0.
- Dates: end_date >= start_date when both present; is_current=true implies end_date NULL.
- Uniqueness: one run_resume_selections per run_id; one resume_contacts per resume_id.
- Cross-user protection: run_resume_selections.user_id must equal resumes.user_id.

#### Indexing (Cosmos DB logical guidance)
- resumes: compound on (user_id, is_deleted, updated_at desc); filter on processing_status; unique on (user_id, id).
- Child tables: index resume_id; order by order_index.
- run_resume_selections: unique on run_id; index (user_id, created_at desc).
- resume_parse_events: index resume_id, created_at desc.

#### Edge Cases
- Re-upload same file: use checksum_sha256 to flag duplicates per user; allow but mark via parse event.
- Failed parse: keep record with processing_status='failed' and parsing_error; editing still allowed.
- Deleting an active resume: allowed; existing run selection remains historical, but new selections must reject deleted resumes.
- Partial parses: allow empty child sets; validated=false until user fixes.

---

## Frontend

### Frontend PRD: Resume Management
**Feature:** Resume Management  
**Type:** frontend

### Resume Management

#### Feature overview
Allows job seekers to upload resumes (PDF/DOCX), parse them into a structured schema, correct parsing errors, manage a library of resumes, and select which resume to use per application run. Ensures reliable, editable machine-readable data while preserving the original file.

#### Scope & behavior
- Supported files: PDF, DOCX. Max size: 10 MB. Max pages: 10. Reject password-protected or corrupted files.
- Storage: Preserve original file; maintain parsed JSON snapshot and parse status per resume.
- Parse status states:
  - Queued → Parsing → Parsed (Ready) or Needs review or Failed.
  - Display status badges and last updated timestamp.
- Duplicates: If uploaded file hash matches an existing resume, prompt to keep both (allow rename) or cancel.
- Validation (Edit UI):
  - Required: Full name, at least one contact method (email or phone), at least one experience OR education entry.
  - Email format, phone E.164 or common local formats, URLs valid https.
  - Dates: start ≤ end; allow “Present” for end.
  - Skills: free text tags; max 100 chars/tag; up to 100 tags.
  - Text fields length caps: role/company/school 200 chars, section descriptions 4000 chars.
- Permissions: Only the authenticated owner may view/edit/delete/set active.
- Deletion: Allowed unless resume is locked by an in-progress run; show reason and disable Delete.
- Active resume per run: During “Apply Run” kickoff, user must choose one resume; default to last used Ready resume. Cannot select resumes with status Failed or Queued/Parsing. Needs review is selectable but warns user to review first.
- Accessibility: All controls keyboard-navigable; labels, ARIA roles; color not sole status indicator.

#### User-facing flows
- Upload Resume
  1. From Library, click “Upload” or drag-and-drop.
  2. Client validates type/size; on pass, shows uploading progress.
  3. On success, resume row appears as Queued then transitions; toast shown.
  4. On password-protected/corrupt/size error: inline error with guidance; file not added.
  5. On duplicate: modal to Keep both (rename inline) or Cancel.

- Parse to Schema
  - Status auto-updates. If Failed: show “Retry parse” action.
  - If Needs review: badge + CTA “Review & fix” opens editor with highlighted fields missing/low confidence.

- Edit & Validate
  - Editor sections: Profile (name, contact, location, links), Summary, Skills (tags), Experience (repeatable entries: title, company, location, start/end, description bullets), Education (repeatable: school, degree, field, start/end, notes), Certifications (optional).
  - Inline validation on blur; summary validation on Save.
  - Unsaved changes guard on navigate away; buttons: Save, Cancel.
  - Save updates parsed JSON and recalculates status to Ready if all required fields valid.

- Library Management
  - List view (table/cards): Name, File type, Status badge, Last updated, Used in runs (count), Actions: Preview, Edit, Set as default for next run (optional toggle), Delete (if allowed).
  - Preview: Side panel with two tabs: Original (embedded viewer or download link if unsupported) and Parsed (read-only structured view).
  - Search by name; filters by status and file type; sort by updated.

- Set Active Resume (Per Run)
  - In Apply Run modal/step: dropdown/list of Ready and Needs review resumes with status chips; quick Preview link.
  - Selection is mandatory; remembers last selection for next run.

- Errors/edge cases
  - Long parse times: show “Still parsing…” with spinner; auto-refresh every 5s; manual refresh.
  - Network errors: retry affordance; non-blocking toasts with detail.
  - File name conflicts: allow rename on upload or later.

#### Acceptance criteria
- User can upload valid PDF/DOCX ≤10 MB and see it appear with Queued status within 2s of upload completion.
- Password-protected, corrupted, or oversized files show descriptive inline errors; no library entry created.
- Duplicate uploads prompt with options; choosing Keep both creates a new entry with unique name.
- Parse status transitions visibly update without full page reload; Failed resumes show Retry parse; retry re-queues parse.
- Needs review resumes open editor highlighting invalid/missing required fields; Save enforces validation and updates status to Ready when passing.
- Editor prevents navigation with unsaved changes unless user confirms discard.
- Library shows accurate metadata, supports search/filter/sort, and actions (Preview, Edit, Delete) per row.
- Preview displays original (or download link fallback) and parsed JSON as human-readable sections.
- Delete action requires confirmation; blocked if resume is in-use by in-progress run; user sees reason.
- Apply Run requires selecting a resume; non-selectable statuses are disabled with tooltip; last used Ready resume is preselected when available.
- All interactive elements are keyboard accessible; status has text labels in addition to color.

#### Out of scope
- Resume authoring/generation, template design, or formatting controls.
- Cover letters or portfolio attachments.
- Multi-language parsing, OCR of images, or image-based resumes.
- Backend parsing quality improvements beyond UI feedback and retry.
- Bulk imports from cloud drives.
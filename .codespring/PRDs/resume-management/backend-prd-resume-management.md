# Backend PRD: Resume Management
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
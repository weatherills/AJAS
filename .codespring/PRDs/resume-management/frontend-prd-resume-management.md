# Frontend PRD: Resume Management
**Feature:** Resume Management  
**Type:** frontend

# Resume Management

## Feature overview
Allows job seekers to upload resumes (PDF/DOCX), parse them into a structured schema, correct parsing errors, manage a library of resumes, and select which resume to use per application run. Ensures reliable, editable machine-readable data while preserving the original file.

## Scope & behavior
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

## User-facing flows
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

## Acceptance criteria
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

## Out of scope
- Resume authoring/generation, template design, or formatting controls.
- Cover letters or portfolio attachments.
- Multi-language parsing, OCR of images, or image-based resumes.
- Backend parsing quality improvements beyond UI feedback and retry.
- Bulk imports from cloud drives.
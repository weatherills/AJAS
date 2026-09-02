# Database PRD: Resume Management
**Feature:** Resume Management  
**Type:** database

## Feature Summary
Database schema for Resume Management in AJAS: store uploaded resume files, parse into structured entities (skills, experience, education), allow edits with validation metadata, manage library state (list/preview/delete), and select an active resume per application run.

## Entities & Relationships
- resumes (parent) — one record per uploaded resume version per user; stores file metadata, processing state, validation flags, and preview.
- resume_contacts — optional 1:1 contact/profile info for a resume.
- resume_skills — 1:N skills linked to a resume.
- resume_experiences — 1:N work history entries linked to a resume.
- resume_educations — 1:N education entries linked to a resume.
- run_resume_selections — maps a run to the chosen resume (exactly one per run). Prevents use of deleted resumes.
- resume_parse_events — append-only log of ingestion/parsing/edit events for observability.

## Core Behaviors
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

## Constraints & Validation
- resumes.user_id required.
- processing_status in {uploaded, queued, parsing, parsed, failed}.
- File constraints: mime_type in {application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document}; file_size > 0.
- Dates: end_date >= start_date when both present; is_current=true implies end_date NULL.
- Uniqueness: one run_resume_selections per run_id; one resume_contacts per resume_id.
- Cross-user protection: run_resume_selections.user_id must equal resumes.user_id.

## Indexing (Cosmos DB logical guidance)
- resumes: compound on (user_id, is_deleted, updated_at desc); filter on processing_status; unique on (user_id, id).
- Child tables: index resume_id; order by order_index.
- run_resume_selections: unique on run_id; index (user_id, created_at desc).
- resume_parse_events: index resume_id, created_at desc.

## Edge Cases
- Re-upload same file: use checksum_sha256 to flag duplicates per user; allow but mark via parse event.
- Failed parse: keep record with processing_status='failed' and parsing_error; editing still allowed.
- Deleting an active resume: allowed; existing run selection remains historical, but new selections must reject deleted resumes.
- Partial parses: allow empty child sets; validated=false until user fixes.

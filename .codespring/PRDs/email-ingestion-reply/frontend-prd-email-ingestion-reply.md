# Frontend PRD: Email Ingestion & Reply
**Feature:** Email Ingestion & Reply  
**Type:** frontend

# Email Ingestion & Reply — Frontend/UI PRD

## Feature overview
Enable users to view and respond to recruiter emails related to tracked Job Postings/Applications directly in AJAS. Surface auto-linked threads per job, show attachments, and provide a streamlined reply composer with templates and AI suggestions to accelerate communication without leaving the app.

## Scope & behavior
- Supported mailbox: Microsoft 365 Outlook via Microsoft Graph (single connected account per user).
- Locations:
  - Job Details page: Emails tab with thread list and message view.
  - Global “Email” panel (optional entry): lists recent job-linked threads across all jobs.
- States:
  - Not connected: prompt to “Connect Microsoft 365 Email” with OAuth CTA.
  - Connected, no emails: empty state with “No emails yet. Try Refresh.”
  - Loading/syncing: spinner with last sync timestamp.
  - Error: inline banner with retry and error details (rate limit, expired token).
- Permissions/validations:
  - Only owner of the connected mailbox can view/send.
  - Reply requires non-empty body; max 25 MB total attachments; up to 20 files; supported formats shown.
- Thread linking:
  - Auto-linked threads displayed under the corresponding Job Posting/Application.
  - If message cannot be confidently linked, show “Unlinked” badge with “Link to job” control (searchable job picker); allow unlink from a job.
- Privacy/Safety:
  - Show clear “From: your@domain.com” (read-only).
  - Confirm dialog when sending to multiple recipients or with empty subject.
- Accessibility:
  - Keyboard navigation for thread list, message view, composer.
  - ARIA labels for actions; contrast AA; focus states visible.

## User-facing flows
1. Connect email (first run)
   - User sees connect card on Emails tab.
   - Click “Connect Microsoft 365” → opens OAuth (new window).
   - On success: show initial sync in progress; threads appear progressively with timestamped “Last synced”.

2. View threads for a job
   - Emails tab shows thread list (left): each item shows subject, participants, last message snippet, relative time, unread badge.
   - Selecting a thread opens message view (right): messages in chronological order (latest at bottom), with sender, time, rich-text body, and attachments.
   - Unread messages mark as read when viewed.

3. Manual link/unlink
   - For an “Unlinked” message: click “Link to job” → modal with job search (title/company) → select → toast “Linked to [Job]”.
   - From a linked thread: overflow menu → “Unlink from job” (with confirm).

4. Reply in-app
   - Click “Reply” at bottom of thread → composer opens inline:
     - Pre-filled To/CC from last message; Subject prefixed “Re:”.
     - Rich text: bold, italic, underline, bullets, hyperlinks; plain-text fallback toggle.
     - Templates dropdown: user/system templates with variable preview (e.g., {Company}, {Role}).
     - AI suggestions: “Generate reply” button; presents 3 suggestions; user can insert/edit.
     - Attach files: drag & drop or “Attach” button; show file chips with size; remove individual files.
     - Send/Cancel buttons; disabled state until validations pass.
   - On Send: show progress; on success, new message appended to thread; toast “Sent”. On error, inline error with “Retry”.

5. Attachments
   - Message attachments: show file type icon, name, size, and actions (Preview where supported: PDF/images; otherwise Download).
   - Reply attachments: enforce size/count limits; show error per file with reason; support removing before send.

## Acceptance criteria
- Emails tab appears on Job Details only when mailbox connected; otherwise shows connect prompt.
- Thread list groups only messages linked to the current job; unread badges clear upon view.
- “Refresh” triggers visible syncing state and updates “Last synced”.
- Unlinked messages can be searched and linked to a job; linked threads display the associated job meta.
- Composer:
  - Prefills recipient(s) and subject; blocks send if body empty.
  - Templates insert content at caret position; variables resolve using job/application context; unresolved variables are highlighted for user edit.
  - AI suggestions return up to 3 options; user can insert one; failure shows non-blocking error.
  - Attachments enforce max 25 MB total and max 20 files; oversize files are rejected with clear messaging.
- Sent replies appear in thread within 5 seconds with pending state that resolves to sent or error.
- Attachment previews work for PNG/JPG/PDF; others offer download only.
- All actions accessible via keyboard; focus order logical; buttons have ARIA labels; contrasts meet WCAG AA.

## Out of scope
- Multiple email accounts, shared mailboxes, or Gmail integration.
- Composing net-new emails not tied to an existing thread.
- Advanced email features: scheduling, signatures management, read receipts, S/MIME, forwarding.
- Bulk operations across threads, tagging/labels, or smart folders.
- Admin delegation and team visibility.
# Frontend PRD: Review & Decision UI
**Feature:** Review & Decision UI  
**Type:** frontend

# Review & Decision UI

## Feature overview
Enables job seekers to quickly review AI-matched or saved job postings, view concise summaries and rationale, and make approve/reject decisions with optional comments. Optimizes throughput via a list + detail pane workflow, AI suggestions, filters, and a lightweight audit trail for learning and traceability.

## Scope & behavior
- Views
  - Match Queue: AI-suggested matches awaiting decision.
  - Saved Queue: User-saved jobs awaiting decision.
  - History & Audit: Read-only list of prior decisions with notes.
  - Toggle via top-level segmented control: Matches | Saved | History.
- List (Match Queue and Saved Queue)
  - Columns: Job Title, Company, Location, Source (AI/Saved), Score (0–100), Applied? (Y/N), Added Date.
  - Filters: Score range slider, Company (typeahead), Location, Source (AI/Saved), Date added, Status (Awaiting/Approved/Rejected).
  - Sort: Score (desc default), Date added, Company, Title.
  - Pagination/infinite scroll (page size 25), total count, empty states with guidance.
  - Selection: Single-select highlights row and opens Detail Pane on the right.
- Detail Pane (sticky/right-side)
  - Header: Title, Company, Location, Link to original posting (opens new tab), Score badge, Status chip.
  - Summary: 3–5 bullet highlights from job and resume match; “Why it matches” explanation from AI Matching Service; show last refreshed timestamp.
  - AI Suggestion: “Recommend Approve/Reject/Review” with confidence; show rationale (max 400 chars); fallback to “No suggestion available” if missing.
  - Resume Highlights: Top skills matched/missing; years experience alignment; keywords. If resume not available, show “Resume not found” state.
  - Approve/Reject controls: Two primary buttons; inline comment input (up to 1,000 chars) with placeholder (“Add notes for your future self (optional)”).
  - Decision persistence: On click, disable buttons, show spinner; on success, update Status chip, remove from queue list, show toast. On failure, re-enable, show error toast with retry.
  - Keyboard shortcuts: A = Approve, R = Reject, Cmd/Ctrl+Enter = Save decision with comment focused.
- History & Audit
  - List columns: Job Title, Company, Decision (Approved/Rejected), Comment (truncated), Decided Date/Time, Source (AI/Saved), Score at decision.
  - Row click opens read-only Detail Pane with the state at decision time (as stored); if historical snapshot missing, show current data with “Snapshot unavailable” note.
  - Reconsider action: “Reopen” button moves the item back to the appropriate queue as Awaiting Decision; original audit entry remains immutable, and a new history entry will be created on new decision.
- Validations & errors
  - Comments optional for both approve/reject; trim whitespace; block >1,000 chars with counter and error.
  - Network/API errors: inline error in pane + toast; no data loss in comment field.
  - Permissions: Single-user scope (MVP). Only the signed-in user can view/edit their own queues and history.
- Accessibility & responsiveness
  - Fully keyboard navigable (tab order: list → pane → actions), visible focus states, ARIA roles for list, pane, and status updates.
  - Contrast-compliant badges and buttons.
  - Responsive: ≥1024px shows list + pane; <1024px shows list, tapping a row navigates to full-screen detail with top-back control. Decision buttons sticky at bottom on mobile.

## User-facing flows
1. Review a match
   - Open Matches → filter by Score >70 → select row → read Summary/Suggestion → add optional comment → Approve or Reject → toast “Decision saved” → next row auto-selected (or pane closes on mobile).
2. Review saved job
   - Open Saved → select row → decide → item removed from Saved queue on success.
3. Failure state
   - Click Approve → network error → buttons re-enabled, error toast “Could not save decision. Try again.” → user retries without losing comment.
4. View history and reconsider
   - Open History → inspect decision details → click Reopen → item appears in Matches or Saved (based on original source) with status Awaiting.

## Acceptance criteria
- Lists render with defined columns, filters, sort, pagination; empty states show actionable guidance.
- Selecting a row opens Detail Pane with summary, score, suggestion, and resume highlights (with appropriate fallbacks).
- Approve/Reject actions persist status and comment; UI disables during save; on success, item leaves queue and toast confirms.
- Comment input enforces 0–1,000 characters, shows remaining count and validation errors.
- Keyboard shortcuts A/R/Cmd+Enter function and are discoverable via tooltip or help hint.
- History displays immutable past decisions with timestamp, comment, score; missing snapshots show clear notice.
- Reopen moves item to Awaiting and retains original history entry.
- All views function on desktop and mobile per responsive rules; decision buttons remain reachable.
- Accessibility: focus management after decision, ARIA live region announces status updates, minimum contrast 4.5:1.

## Out of scope
- Editing or deleting past decisions or comments.
- Bulk approve/reject.
- Metrics dashboards, exports, or notifications.
- Resume editing or job scraping within this UI.
- Multi-user collaboration or role-based permissions.
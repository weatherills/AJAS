# Frontend PRD: Learning Loop
**Feature:** Learning Loop  
**Type:** frontend

# Learning Loop — Frontend PRD

## Feature overview
Enable users to provide explicit feedback on AI job matches (approve/reject with optional comments) and visualize how the system adapts over time. Provide a simple control for match strictness (manual or auto-tuned) and a lightweight metrics view to build trust and transparency. All interactions are per-user and affect future match ranking only.

## Scope & behavior
- Surfaces
  - On Match List/Detail: Approve and Reject actions with optional comment capture.
  - Preferences → Matching: “Tuning mode” and “Match strictness” control.
  - Learning panel: Basic metrics over time with status of auto-tuning.
- States
  - Actions: idle, submitting, success (with 5s undo), error (retry).
  - Metrics: loading, loaded (with data), empty (no decisions), error.
  - Tuning: Auto (read-only strictness + info text), Manual (editable strictness).
- Validations
  - Comments optional; max 500 chars; trimmed; block submission of only whitespace.
  - One decision per match per user; subsequent clicks on the same match replace the prior decision (with confirm modal).
  - Strictness slider yields discrete levels: Conservative (0), Balanced (1), Adventurous (2).
- Errors
  - Network/API failure: non-blocking toast with “Retry” and preserves local state for 30 min to re-send.
  - Comment save failure does not revert the decision; show inline warning on the comment field.
- Permissions
  - Authenticated users only. All UI hidden for signed-out users.
- Accessibility
  - Approve/Reject are buttons with aria-labels, visible focus states, and keyboard operable (Tab + Space/Enter).
  - Undo exposed as a button, not only toast text. Color use paired with icon/text.
  - Metrics charts include textual summaries for screen readers.

## User-facing flows
- Decision Logging
  1. User clicks Approve or Reject on a match card or detail.
  2. Inline comment input expands (optional). User may type and hit Save, or dismiss.
  3. UI sends decision event; optimistic state applied (badge on card + subdued opposite action).
  4. Success: show toast “Recorded. Undo” (5s). Undo reverts local state and sends reversal event.
  5. Error: revert optimistic state, show error toast with Retry. Retry resubmits last payload.
  - Edge cases:
    - Double-clicks coalesced; disable buttons while submitting.
    - Changing decision later prompts: “Replace your previous decision?” [Replace/Cancel].
- Weight/Threshold Tuning
  1. Preferences → Matching.
  2. Tuning mode: Auto (default) or Manual.
     - Auto: strictness slider is disabled; helper text “Adjusted from your last 30 decisions.”
     - Manual: slider enabled; selecting level shows preview helper “Fewer matches, higher precision” (Conservative) / “Balanced” / “More matches, higher recall” (Adventurous).
  3. Save shows non-blocking confirmation “Preferences updated. Takes effect on new suggestions.”
  - Edge cases:
    - No decisions yet in Auto: banner “We’ll adapt after your first few choices.”
- Basic Metrics
  - Panel on Dashboard and within Preferences:
    - Approve rate (last 7d)
    - Decision volume (last 7d)
    - Trend sparkline of approve rate (7d) with % delta vs prior 7d
    - “Exposure strictness” current level and whether Auto or Manual
  - Empty state: “No learning signals yet. Start by reviewing matches.”
  - Time range toggle: 7d (default) / 30d persists in local storage.

## Acceptance criteria
- Approve/Reject buttons render on every match card/detail when signed in; hidden when signed out.
- Clicking Approve/Reject updates the card to show selected state, disables both buttons during submit, and shows undo toast on success.
- Optional comment input supports up to 500 visible characters and prevents whitespace-only submission.
- Re-deciding on the same match triggers a confirm modal; choosing Replace updates UI and logs new decision.
- Errors surface via toast; Retry resubmits and restores optimistic state on success.
- Preferences screen shows Auto (default) with disabled slider; switching to Manual enables slider with three discrete labeled stops.
- Saving preferences updates the visible strictness indicator across UI and persists across sessions.
- Metrics panel loads asynchronously; shows correct zero state when the user has no decisions; includes textual summary for screen readers.
- Keyboard and screen reader users can operate all decision controls, Undo, and preferences without a mouse.

## Out of scope
- Displaying raw model weights or exact thresholds.
- Team/organizational aggregation or leaderboards.
- Advanced analytics (ROC curves, per-feature attribution).
- Editing or deleting historical comments beyond immediate Undo window.
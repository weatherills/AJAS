# Frontend PRD: Matching & Ranking
**Feature:** Matching & Ranking  
**Type:** frontend

## Feature overview
Display an AI-generated match percentage between a user’s resume and a job posting, combine keyword and semantic signals, and present a brief rationale. Allow users to configure a minimum match threshold that governs which results are flagged as “save-worthy” and persisted. Surface model/version info to ensure reproducibility and clarity when scores change.

## Scope & behavior
- Match score display
  - Normalized 0–100%, integer by default (e.g., 82%). Optional single-decimal on hover tooltip.
  - Color states: 0–49 red, 50–69 amber, 70–100 green. Do not rely on color alone; include label (e.g., “Good match”).
  - States: loading (skeleton badge), computed, error (dash “—” with tooltip).
- Keyword + Semantic scoring overview
  - Tooltip/expand shows weighted breakdown: “Keywords 40% • Semantic 60%” and top 5 matched entities/phrases.
  - Chip group: up to 6 highlighted keywords/phrases; remaining collapsed under “+X more.”
- Explanation summary
  - Collapsible section “Why this score” with a 2–4 sentence rationale.
  - Truncate at 600 chars with “Show more” to expand up to 2000 chars. Preserve line breaks.
- Configurable threshold
  - User setting (default 70%). Slider (0–100) + numeric input. Changes persist immediately.
  - Threshold affects UI badges (“≥ threshold” shows “Meets Threshold” tag) and determines which matches are auto-saved/prompted to save.
  - On job lists: optional filter toggle “Only show ≥ threshold.”
  - Threshold is per-user; read-only for non-authenticated users (hide control).
- Normalization & versioning
  - Info icon reveals: model name, version, profile, last computed timestamp (UTC), and normalization range (0–100%).
  - If a score was computed with an older model, show subtle “Outdated” pill with tooltip “Recomputed with vX.Y may differ.”
- Error/edge validations
  - If resume missing: show neutral score state with CTA “Add resume to see match.”
  - If job text insufficient: show “Not enough data to score.”
  - Network/compute error: retry button; non-blocking for page interactions.
- Permissions
  - Available to signed-in job seekers. Threshold setting gated to authenticated users.

## User-facing flows
- Job list
  - Each job card shows: Match badge (percent + color + label), Meets Threshold tag if applicable.
  - Hover/click on badge opens breakdown tooltip. Clicking “Why this score” opens side panel/modal with full explanation summary.
  - “Only show ≥ threshold” toggle filters list client-side (when scores are available).
- Job detail
  - Prominent match meter (circular or bar), percentage, label, Meets Threshold tag.
  - Explanation section collapsed by default. “View model/version” info icon near the meter.
  - If ≥ threshold: auto-select “Save match” checkbox; otherwise unchecked. User can override.
- Settings > Matching
  - Slider + numeric input (0–100). Input validates integers 0–100; out-of-range shows inline error, disables Save.
  - Save feedback: inline success “Threshold updated.”

## Acceptance criteria
- Scores render as integers 0–100; color and textual label align with ranges.
- Tooltip shows keyword/semantic weights and up to 5 top terms; overflow grouped.
- Explanation summary truncates to 600 chars with “Show more”; expands smoothly; ESC closes modal/panel.
- Threshold changes persist and immediately update Meets Threshold tags across current views.
- List filter hides items below threshold without layout shift jank (use height placeholders while filtering).
- Missing resume shows neutral state with CTA; no percentage displayed.
- Model/version info visible via info icon; outdated scores show “Outdated” pill.
- All interactive elements keyboard accessible (Tab/Shift+Tab), focus-visible, tooltips on focus and hover.
- Contrast ratio ≥ 4.5:1; color not sole indicator of state.
- Loading uses skeletons for badge and meter; errors show tooltip and retry.

## Out of scope
- Backend scoring algorithms, weight tuning, or re-computation scheduling.
- Resume parsing/editing and job content enrichment.
- Notifications or recommendations driven by match changes.
- Team/org-level threshold policies or A/B experiments.
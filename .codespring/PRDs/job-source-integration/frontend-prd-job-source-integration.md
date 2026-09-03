# Frontend PRD: Job Source Integration
**Feature:** Job Source Integration  
**Type:** frontend

# Feature overview
Unified job feed that fetches public postings from Greenhouse and Lever, deduplicates overlapping entries, and surfaces stable, rate-limit-aware sync status. Users see a single, clean list with source badges, filters, and reliable on-demand refresh without duplicates or noisy errors.

## Scope & behavior
- Surfaces
  - Job Feed page: unified list of postings.
  - Filters: source (Greenhouse, Lever), location (string), role/title (string), and status (new since last visit).
  - Source status bar: per-source last sync time, status (OK, syncing, rate-limited, error), manual refresh.
  - Job details drawer: expanded details and apply links.
  - Dedup presentation: merged job card with “Also from …” indicator.

- Data states
  - Idle: list displays cached results; last sync time visible.
  - Syncing: spinner in status bar and skeleton loaders for list if first load; otherwise incremental.
  - Rate-limited (soft): source shows “Temporarily limited” with countdown; user refresh disabled per source until backoff expires; auto-resume post backoff.
  - Error: non-blocking banner per source; list continues with other sources if available.
  - Empty: “No jobs found” with guidance to adjust filters and a refresh CTA.

- Pagination
  - Infinite scroll (default): fetch next page at 80% scroll. Each fetch ≤ 25 jobs (post-dedupe). Show bottom loader; stop when no more pages.
  - Fallback pagination (accessibility toggle): numbered pages with 25/page, Next/Prev buttons.

- Deduplication UI
  - Merge entries with same canonical key (company + role/title + location + externalId hash). One primary card shown.
  - Display “Also found on Lever/Greenhouse” chip(s) with count. Tooltip shows per-source posted date and source URL domain.
  - Details drawer includes a Sources section listing all matched sources with links; primary source chosen by freshness (newest updatedAt).
  - Searching/filtering operates on merged entities; counts reflect merged set.

- Filters & search
  - Source filter: multi-select chips (default: all).
  - Free-text search applies to title, location, company.
  - Filters persist per session (local storage) and apply before pagination requests.
  - Clear All resets to defaults and triggers refetch.

- Rate limiting & backoff UX
  - Manual refresh button per source; disabled with countdown if backoff active (mm:ss).
  - Global Refresh All respects per-source availability; partial refresh allowed.
  - Tooltips explain cooldown when disabled.

- Scheduler visibility
  - Status bar indicates when a background crawl run is active (“Syncing…”) and per-source progress (e.g., page 2/5 when provided; otherwise spinner).
  - Client polls status endpoint every 15s with exponential backoff to 60s when idle; stops when tab hidden.

- Job details
  - On selecting a card, details drawer loads details lazily; show skeleton then content. If source details fetch fails, show partial card data with inline warning and alternative source link if available.

- Permissions
  - Public read-only. No sign-in required.

- Responsive & accessibility
  - Mobile: one-column list; sticky bottom Refresh button; filters in a bottom sheet.
  - Tablet/desktop: two-pane option (list + drawer) ≥ 1024px; filters in left rail ≥ 768px.
  - Keyboard: full navigation (Tab through filters, list; Enter to open drawer; Esc to close).
  - ARIA: live region for sync status changes; appropriate roles for list/listitem; buttons labeled with source and action.
  - Color-contrast AA; focus visible; spinner accompanied by text.

## User-facing flows
- Initial load
  1. Render cached feed instantly if available.
  2. Kick off background sync; status bar shows Syncing per source.
  3. Merge new results; update list incrementally without scroll jump.

- Manual refresh (per source or all)
  1. User clicks Refresh. If not rate-limited, trigger sync; else show countdown tooltip.
  2. Status updates. On completion, toast “Greenhouse updated: 12 new jobs” (if >0) or “No new jobs.”

- Infinite scroll
  1. User scrolls; when threshold hit, fetch next page.
  2. If rate-limited mid-scroll, stop auto-fetch for that source; continue with others; show inline “Waiting due to rate limit” message; Resume automatically after cooldown.

- Dedup interaction
  1. User opens a merged job; sees Sources list.
  2. Selecting a different source link opens that source’s posting in a new tab.

- Error handling
  - If Greenhouse fails: banner “Greenhouse fetch failed. Retrying soon.” with non-blocking retry indicator; Lever continues.
  - Network offline: show offline toast; allow viewing cached list; disable refresh; auto-retry on reconnect.

## Acceptance criteria
- Feed shows a combined, deduplicated list with source chips; no duplicate cards from same role/company/location set.
- Source filter toggles correctly update results and counts without duplicates resurfacing.
- Infinite scroll loads additional pages and stops at end; accessible pagination alternative available and keyboard-operable.
- Status bar displays per-source states: OK, Syncing, Rate-limited (with visible mm:ss), Error, with accurate last sync timestamps.
- Manual refresh disabled during active backoff; tooltip explains remaining time; automatic re-enable when countdown reaches 0.
- Background sync updates list without resetting scroll position; new items can be highlighted as “New” since last visit.
- Details drawer loads lazily with skeleton; shows Sources section with multiple source links when deduped; handles partial failure gracefully.
- Offline mode shows cached data and disables refresh; on reconnect, auto-refresh triggers and UI updates.
- All interactive elements are keyboard accessible; ARIA live region announces “Syncing started/completed,” “Rate limit active,” and error banners.
- Mobile layout preserves core functionality; sticky Refresh button visible; filters accessible via bottom sheet.
- No PII or auth prompts appear; feature functions with public endpoints only.

## Out of scope
- Authenticated/private postings, employer logins, or OAuth with ATS.
- Applying to jobs, saving, alerts/notifications, or recommendations UI.
- Admin tooling to manage crawl schedules or source credentials.
- Editing dedup rules from UI; manual merge/split of jobs.
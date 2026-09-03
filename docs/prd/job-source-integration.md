# Job Source Integration — Product Requirements

> **Runbook phase:** Phase 5 &nbsp;·&nbsp; **Feature key:** `job-source-integration`
>
> Consolidated PRD for the "Job Source Integration" feature — combines the backend,
> database, and frontend requirements in one place. The canonical,
> CodeSpring-generated sources remain the source of truth:
> - [Backend PRD](../../.codespring/PRDs/job-source-integration/backend-prd-job-source-integration.md)
> - [Database PRD](../../.codespring/PRDs/job-source-integration/database-prd-job-source-integration.md)
> - [Frontend PRD](../../.codespring/PRDs/job-source-integration/frontend-prd-job-source-integration.md)

---

## Backend

### Backend PRD: Job Source Integration
**Feature:** Job Source Integration  
**Type:** backend

Feature overview
Job Source Integration ingests public job postings from Greenhouse and Lever into AJAS on a recurring, event-driven schedule. It normalizes, deduplicates, and persists postings for downstream matching and user surfacing. The system respects source rate limits, retries transient failures with backoff, and scales to zero when idle.

Scope & behavior
- Sources
  - Greenhouse: Fetch list of jobs (with pagination and optional filters), then fetch job details per posting.
  - Lever: Fetch list of jobs via public endpoints, then fetch details per posting if available/required.
- Source configuration (Cosmos DB collection: job_sources)
  - id, type ∈ {greenhouse, lever}, base_url (board URL), filters (optional: department, team, location, work_type), crawl_interval_minutes, enabled (bool), last_run_at, status.
  - base_url must be HTTPS and match an allowlist pattern for each provider (prevent SSRF).
- API (internal/admin; Azure Functions HTTP, JWT-protected)
  - POST /sources/{id}/crawl: Enqueue a crawl run for a single source. 202 with run_id.
  - GET /sources/{id}/runs/{run_id}: Return run status {queued|running|succeeded|failed|partial}, counts, error summary.
- Scheduler
  - Timer-triggered Function evaluates enabled sources due for crawl and enqueues crawl-run messages to Azure Storage Queue: crawl-runs.
  - Scale-to-zero friendly: no long-lived workers; fan-out via queues.
- Crawl workflow (event-driven)
  - A crawl-run function dequeues run messages, discovers listing pages (paginate until exhausted), enqueues per-job fetch tasks to job-fetch queue.
  - Per-job fetch function retrieves details, normalizes schema, persists raw and normalized data, and performs deduplication logic.
  - Completion aggregation updates run status and metrics.
- Rate limiting & backoff
  - Per-source concurrency: max 3 in-flight HTTP requests per domain.
  - Client-side rate: ≤3 RPS per source; global cap 10 RPS across all sources.
  - 429/503/504: exponential backoff with jitter (initial 1s, factor 2, max 60s), up to 5 retries; respect Retry-After if present.
  - Network timeouts: 10s connect, 20s read; 3 retries for idempotent GETs.
- Data model (Cosmos DB collection: job_postings)
  - Fields: id (canonical_id), source_type, source_job_id, source_url, company_name, company_domain, title, locations (array normalized), remote (bool|null), employment_type, posted_at, updated_at_source, apply_url, description_text, description_html_blob_url, tags (dept/team), first_seen_at, last_seen_at, active (bool), content_hash (SHA256 over normalized title+company+locations+employment_type+apply_url+description_text), raw_blob_url, run_id_last_updated.
  - Raw payloads stored in Blob Storage under /raw/{source_type}/{source_id}/{source_job_id}.json with ETag/Last-Modified for change detection.
- Deduplication
  - Canonical key: lower(title) + normalized_company_domain + normalized_primary_location + normalized_apply_url host/path.
  - Upsert by canonical_id = sha1(canonical key).
  - If existing canonical_id found and content_hash unchanged -> no-op except update last_seen_at.
  - If content_hash changed -> update document, set updated_at_source, keep history by writing previous raw to versioned blob path.
  - Cross-source duplicates merged via same canonical_id derivation; preserve source provenance in an array if needed in future (MVP: last-writer-wins with source_type/source_job_id tracked).
  - Deactivation: if a job was seen previously but not present in two consecutive successful crawls, set active=false and update last_seen_at.
- Validation
  - Reject postings missing title, company, apply_url (skip and log).
  - Normalize locations (city, region, country) and strip HTML to description_text.
  - Truncate overly long fields to Cosmos limits; store full HTML in Blob.
- Permissions & security
  - All HTTP Functions require app role JWT; queue-triggered functions use managed identity.
  - Strict allowlist for base_url by provider; no arbitrary host fetching.
  - PII: store only public posting data; redact emails in descriptions when hashing.
- Performance & observability
  - Throughput target: 10k postings/hour with ≤500ms avg per job-fetch excluding backoff.
  - Idempotent processing: dedupe ensures replays do not create duplicates.
  - Structured logs with run_id/source_id; metrics: fetched, upserts, no-ops, deactivations, errors, rate-limited events.
  - Poison queues for messages failing >10 attempts.

User-facing flows
- Periodic ingestion
  - Scheduler enqueues runs -> listings fetched with pagination/filters -> per-job details fetched -> dedupe/upsert -> new/updated jobs available to feed.
- On-demand refresh (admin)
  - Admin calls POST /sources/{id}/crawl -> run executes as above -> status polled via GET run status.
- Edge cases
  - Source down: run marked partial/failed; retries applied; no stale jobs deactivated unless at least one successful listing fetch occurred.
  - Pagination anomalies (duplicate pages/missing next): stop on repeated page tokens or HTTP 404; ensure idempotency by dedupe.

Acceptance criteria
- Greenhouse: system can fetch paginated listings and per-job details using base_url; supports optional department/location filters when configured.
- Lever: system can fetch public postings and details; handles non-paginated and paginated responses.
- Rate limiting enforced at configured RPS; 429/5xx cause exponential backoff with Retry-After honored.
- Deduplication prevents duplicate Cosmos records for the same role across sources; unchanged jobs do not update write timestamps except last_seen_at.
- Raw source payloads stored in Blob; normalized records upserted in Cosmos with stable canonical_id.
- Jobs absent in two consecutive successful crawls are marked active=false.
- Scheduler triggers runs only when due; system scales to zero when idle; no stuck messages; poison queue populated on repeated failures.
- Admin API endpoints are JWT-protected and return correct statuses/payloads.
- All network calls time out and are retried per policy; no unbounded retries.

Out of scope
- Scraping non-Greenhouse/Lever sites or private APIs.
- UI/notifications, matching logic, or user feed rendering.
- Source onboarding UI; manual configuration management beyond specified endpoints.
- Applying to jobs or tracking application state.
---

## Database

### Database PRD: Job Source Integration
**Feature:** Job Source Integration  
**Type:** database

##### Feature Summary
Schema to ingest job postings from Greenhouse and Lever, enforce per-source/tenant rate limits and backoff, persist raw payloads, normalize and deduplicate into canonical postings, and support an event-driven scheduler that scales to zero when idle.

##### Entities & Relationships
- job_sources (seeded: greenhouse, lever) → 1:M source_tenants (each org/subdomain/board token)
- source_tenants → 1:M source_fetch_runs (per crawl execution)
- source_fetch_runs → 1:M fetch_requests (HTTP attempts, including retries)
- source_tenants ↔ fetch_cursors (latest pagination/sync state per endpoint)
- source_tenants → 1:M job_postings_raw (raw listing snapshots; multiple per posting over time)
- job_postings_raw → M:1 job_postings_canonical via job_posting_links (dedup across sources/tenants)
- source_tenants ↔ source_rate_limits (distributed token-bucket/backoff state)
- source_tenants ↔ crawl_schedules (next-run hints; scheduler reads and triggers runs)

##### Constraints & Indexing
- Uniqueness:
  - job_postings_raw: unique (source_tenant_id, source_posting_id) when is_current = true.
  - job_posting_links: unique (raw_id) to enforce single canonical mapping per raw record.
  - fetch_cursors: unique (source_tenant_id, endpoint).
  - source_tenants: unique (source_id, tenant_key).
- Dedup keys:
  - Canonical key: lower(trim(title)) + normalized(location) + dedupe_namespace (tenant or company) → normalized slug.
  - dedupe_hash: SHA-256 over canonical key + normalized description/body + employment_type.
  - job_postings_raw.response_hash supports change detection; dedupe_hash supports canonical merge.
- Indexing (logical):
  - job_postings_raw: idx on (source_tenant_id, source_posting_id), dedupe_hash, is_current, seen_last_at desc.
  - job_postings_canonical: idx on canonical_key, dedupe_hash, is_active.
  - fetch_requests: idx on (run_id), (source_tenant_id, request_ts), status_code.
  - source_rate_limits: idx on (source_tenant_id), backoff_until.
  - crawl_schedules: idx on next_run_after where is_paused = false.

##### Operational Flows
- Greenhouse Fetch:
  - Use source_tenant.config (e.g., board_token) to list postings with pagination; persist page cursor in fetch_cursors.endpoint = "list".
  - For each posting, fetch detail; store raw payload in Blob (content_blob_url) and metadata in job_postings_raw; maintain is_current and seen_*.
- Lever Fetch:
  - Public endpoints; similar list→detail. Use subdomain in tenant_key.
- Rate Limiting & Backoff:
  - source_rate_limits stores effective_per_min/burst, tokens_remaining, window_start; update atomically per request.
  - When 429/5xx or provider headers indicate limits, set backoff_until; fetch_requests.rate_limited = true.
- Deduplication:
  - Compute canonical_key and dedupe_hash per raw. If canonical exists (by hash or key), upsert link; else create canonical.
  - Update job_posting_links.confidence and reason to track merge rationale.
- Scheduler:
  - crawl_schedules.next_run_after guides triggering. Each run creates source_fetch_runs, consumes cursors, and updates next_run_after with jitter. Empty deltas allowed; scale-to-zero when no due schedules.

##### Edge Cases
- Posting closed: mark job_postings_raw.is_current = false and set listing_state; update canonical.is_active = false when all linked raws are non-current.
- Content unchanged (response_hash same): update seen_last_at; no new raw record unless status changed.
- Cursor invalid/expired: reset fetch_cursors.cursor = null and log error in source_fetch_runs.error_summary.
- Partial failures: run status = "partial_success" with error_count > 0; retries recorded in fetch_requests.retry_count/backoff_ms.

---

## Frontend

### Frontend PRD: Job Source Integration
**Feature:** Job Source Integration  
**Type:** frontend

### Feature overview
Unified job feed that fetches public postings from Greenhouse and Lever, deduplicates overlapping entries, and surfaces stable, rate-limit-aware sync status. Users see a single, clean list with source badges, filters, and reliable on-demand refresh without duplicates or noisy errors.

#### Scope & behavior
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

#### User-facing flows
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

#### Acceptance criteria
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

#### Out of scope
- Authenticated/private postings, employer logins, or OAuth with ATS.
- Applying to jobs, saving, alerts/notifications, or recommendations UI.
- Admin tooling to manage crawl schedules or source credentials.
- Editing dedup rules from UI; manual merge/split of jobs.
# Backend PRD: Job Source Integration
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
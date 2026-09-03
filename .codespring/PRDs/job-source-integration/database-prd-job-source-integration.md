# Database PRD: Job Source Integration
**Feature:** Job Source Integration  
**Type:** database

### Feature Summary
Schema to ingest job postings from Greenhouse and Lever, enforce per-source/tenant rate limits and backoff, persist raw payloads, normalize and deduplicate into canonical postings, and support an event-driven scheduler that scales to zero when idle.

### Entities & Relationships
- job_sources (seeded: greenhouse, lever) → 1:M source_tenants (each org/subdomain/board token)
- source_tenants → 1:M source_fetch_runs (per crawl execution)
- source_fetch_runs → 1:M fetch_requests (HTTP attempts, including retries)
- source_tenants ↔ fetch_cursors (latest pagination/sync state per endpoint)
- source_tenants → 1:M job_postings_raw (raw listing snapshots; multiple per posting over time)
- job_postings_raw → M:1 job_postings_canonical via job_posting_links (dedup across sources/tenants)
- source_tenants ↔ source_rate_limits (distributed token-bucket/backoff state)
- source_tenants ↔ crawl_schedules (next-run hints; scheduler reads and triggers runs)

### Constraints & Indexing
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

### Operational Flows
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

### Edge Cases
- Posting closed: mark job_postings_raw.is_current = false and set listing_state; update canonical.is_active = false when all linked raws are non-current.
- Content unchanged (response_hash same): update seen_last_at; no new raw record unless status changed.
- Cursor invalid/expired: reset fetch_cursors.cursor = null and log error in source_fetch_runs.error_summary.
- Partial failures: run status = "partial_success" with error_count > 0; retries recorded in fetch_requests.retry_count/backoff_ms.

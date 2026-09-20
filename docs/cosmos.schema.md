# Cosmos DB schema

Generated from `app.storage.catalog` and the Database PRDs.
Unique-key paths omit the partition key (Cosmos unique keys are per partition).
TTL is reserved for transient scrape/ingest/webhook rows; durable history is purged by job.

| Container | Feature | Entity | Partition key | TTL (days) | Unique keys | Composites |
|---|---|---|---|---|---|---|
| `apply_packages` | auto_apply | ApplyPackage | `/auto_apply_id` | — | — | 1 |
| `audit_events` | review | AuditEvent | `/user_id` | — | — | 2 |
| `auto_apply_attempts` | auto_apply | Application | `/user_id` | — | — | 2 |
| `cover_letters` | auto_apply | CoverLetter | `/user_id` | — | — | 1 |
| `crawl_schedules` | job_sources | CrawlSchedule | `/source_tenant_id` | — | — | 1 |
| `decision_events` | review | DecisionEvent | `/user_id` | — | — | 1 |
| `decision_log` | learning | DecisionLog | `/user_id` | — | /recommendation_id | 2 |
| `email_accounts` | mail | EmailAccount | `/id` | — | — | 0 |
| `email_attachments` | mail | EmailAttachment | `/email_account_id` | — | — | 0 |
| `email_connections` | settings | EmailConnection | `/user_id` | — | — | 2 |
| `email_drafts` | mail | EmailDraft | `/email_account_id` | — | — | 0 |
| `email_ingestion_events` | mail | EmailIngestionEvent | `/email_account_id` | 30 | — | 0 |
| `email_link_audits` | mail | EmailLinkAudit | `/email_account_id` | — | — | 0 |
| `email_messages` | mail | EmailMessage | `/email_account_id` | — | /graph_message_id | 3 |
| `email_recipients` | mail | EmailRecipient | `/email_account_id` | — | — | 0 |
| `email_templates` | mail | EmailTemplate | `/id` | — | — | 0 |
| `email_threads` | mail | MailThread | `/email_account_id` | — | /graph_conversation_id | 3 |
| `event_log` | platform | EventLog | `/user_id` | 30 | — | 2 |
| `fetch_cursors` | job_sources | FetchCursor | `/source_tenant_id` | — | /endpoint | 1 |
| `fetch_requests` | job_sources | FetchRequest | `/source_tenant_id` | 30 | — | 3 |
| `form_autofill_values` | auto_apply | FormAutofillValue | `/auto_apply_id` | — | /vendor+/field_key | 1 |
| `graph_subscriptions` | mail | GraphSubscription | `/email_account_id` | — | — | 0 |
| `graph_sync_cursors` | mail | GraphSyncCursor | `/email_account_id` | — | — | 0 |
| `job_posting_links` | job_sources | JobPostingLink | `/raw_id` | — | — | 2 |
| `job_postings_canonical` | job_sources | JobPosting | `/id` | — | — | 3 |
| `job_postings_raw` | job_sources | JobPostingRaw | `/source_tenant_id` | 90 | — | 4 |
| `job_sources` | job_sources | JobSource | `/id` | — | — | 1 |
| `match_explanations` | matching | MatchExplanation | `/match_id` | — | — | 1 |
| `match_runs` | matching | MatchRun | `/user_id` | — | /idempotency_key | 5 |
| `matches` | review | ReviewMatch | `/user_id` | — | /job_id+/resume_id | 7 |
| `metrics_snapshot` | learning | MetricsSnapshot | `/scope_ref` | — | — | 2 |
| `model_params` | learning | ModelParams | `/user_id` | — | — | 1 |
| `model_registry` | matching | ModelRegistry | `/id` | — | — | 1 |
| `recommendations` | learning | Recommendation | `/user_id` | — | — | 3 |
| `resume_parse_events` | resumes | ResumeParseEvent | `/resume_id` | — | — | 1 |
| `resume_variants` | auto_apply | ResumeVariant | `/user_id` | — | — | 1 |
| `resumes` | resumes | Resume | `/user_id` | — | — | 1 |
| `run_resume_selections` | resumes | RunResumeSelection | `/run_id` | — | — | 1 |
| `schema_migrations` | platform | SchemaMigration | `/id` | — | — | 1 |
| `settings_audit_log` | settings | SettingsAudit | `/user_id` | — | — | 2 |
| `source_fetch_runs` | job_sources | SourceFetchRun | `/source_tenant_id` | — | — | 1 |
| `source_rate_limits` | job_sources | SourceRateLimit | `/source_tenant_id` | — | — | 2 |
| `source_tenants` | job_sources | SourceTenant | `/source_id` | — | /tenant_key | 1 |
| `status_events` | auto_apply | StatusEvent | `/auto_apply_id` | — | — | 1 |
| `submit_requests` | auto_apply | SubmitRequest | `/auto_apply_id` | — | /idempotency_key | 4 |
| `user_match_pref_history` | matching | UserMatchPrefHistory | `/user_id` | — | — | 1 |
| `user_match_prefs` | matching | UserMatchPrefs | `/user_id` | — | — | 1 |
| `user_settings` | settings | UserSettings | `/user_id` | — | — | 1 |
| `users` | platform | User | `/id` | — | — | 1 |
| `vendor_field_mappings` | auto_apply | VendorFieldMapping | `/vendor` | — | — | 1 |
| `webhook_callbacks` | auto_apply | WebhookCallback | `/vendor_application_id` | 90 | /dedupe_key | 2 |
| `weight_config` | learning | WeightConfig | `/weight_config_id` | — | — | 1 |
| `weight_tuning_event` | learning | WeightTuningEvent | `/tuning_event_id` | — | — | 1 |

## Query patterns and RU notes

### `apply_packages`

- Query: auto_apply_id point/list
- RU: PK auto_apply_id colocates the frozen package.

### `audit_events`

- Query: match_id + occurred_at
- Query: event_type + occurred_at
- Rel: N—1 matches; UNLOCK_EXPIRED / degraded-view events
- RU: Telemetry volume is higher; composite indexes avoid scans on event_type.

### `auto_apply_attempts`

- Query: user_id + status
- Query: vendor + source_application_id
- Rel: 1—N packages, submits, status_events, webhooks
- RU: Queue of in-flight attempts is a partitioned status filter ~3 RU.

### `cover_letters`

- Query: user_id list
- RU: Metadata + blob uri.

### `crawl_schedules`

- Query: next_run_after where is_paused = false
- RU: Scheduler polls; composite next_run_after + is_paused avoids a full scan.

### `decision_events`

- Query: match_id + decided_at desc
- Rel: N—1 matches; append-only
- RU: History reads stay in the user partition; cheap in-partition queries.

### `decision_log`

- Query: user_id + decided_at desc
- Query: recommendation_id
- Logical unique: `recommendation_id, user_id`
- RU: One decision per recommendation per user via unique key.

### `email_accounts`

- Query: point read by id
- Query: list by user_id
- Logical unique: `id, user_id+provider`
- RU: Few accounts per user; point reads.

### `email_attachments`

- Query: message_id list
- Rel: bytes in Blob; DB stores uri + metadata only
- RU: Metadata only — never index binary.

### `email_connections`

- Query: user+provider
- Query: subscription_expires_at renewals
- Query: account_email lookup
- Rel: N—1 user_settings; tokens excluded from index
- Logical unique: `user_id, provider, status=active`
- RU: Token paths are excluded so encrypted blobs do not inflate the index.

### `email_drafts`

- Query: thread or account list
- RU: Low volume.

### `email_ingestion_events`

- Query: account + created_at desc
- RU: Transient ingest log — 30-day TTL.

### `email_link_audits`

- Query: thread + created_at
- RU: Low volume linking audit.

### `email_messages`

- Query: thread + received_at desc
- Query: delivery_status
- Query: graph_message_id
- Logical unique: `email_account_id, graph_message_id`
- RU: Idempotent Graph ingest relies on unique graph_message_id per account.

### `email_recipients`

- Query: message_id list
- RU: Child rows; queried with parent message.

### `email_templates`

- Query: point read by id
- RU: System templates; PK /id.

### `email_threads`

- Query: account + last_message_at desc
- Query: job_posting_id
- Query: application_id
- Logical unique: `email_account_id, graph_conversation_id`
- RU: Inbox pages of 25 ~5 RU with last_message_at composite.

### `event_log`

- Query: user_id + occurred_at desc
- Query: event_type filter
- Rel: append-only; GDPR writes a delete receipt here
- RU: Append + recent-page queries. Composite keeps 25-item pages under ~5 RU.

### `fetch_cursors`

- Query: tenant + endpoint point read
- Logical unique: `source_tenant_id, endpoint`
- RU: One row per endpoint; always a point read.

### `fetch_requests`

- Query: run_id
- Query: tenant + request_ts
- Query: status_code
- RU: Transient HTTP attempts — 30-day TTL. Indexing status_code is cheap.

### `form_autofill_values`

- Query: auto_apply_id + vendor + field_key
- Logical unique: `auto_apply_id, vendor, field_key`
- RU: Required-field completeness is an in-partition query.

### `graph_subscriptions`

- Query: account point read
- Query: expires_at
- RU: Webhook renewal scan is tiny.

### `graph_sync_cursors`

- Query: account point read
- Logical unique: `email_account_id, mode`
- RU: One cursor document per mailbox.

### `job_posting_links`

- Query: raw_id point read
- Query: canonical_id
- Logical unique: `raw_id`
- RU: PK raw_id enforces one canonical mapping per raw record.

### `job_postings_canonical`

- Query: canonical_key
- Query: dedupe_hash
- Query: is_active
- Rel: 1—N raw via links; 1—N Application/matches
- Logical unique: `canonical_key, dedupe_hash`
- RU: PK /id so dedup lookups use indexed fields (~3 RU) not partition scans.

### `job_postings_raw`

- Query: tenant + source_posting_id
- Query: dedupe_hash
- Query: is_current
- Query: seen_last_at
- Rel: N—1 job_postings_canonical via job_posting_links; payload in Blob
- Logical unique: `source_tenant_id, source_posting_id, is_current=true`
- RU: TTL 90d for scrape snapshots. Unique source_posting_id is per tenant. Body is excluded via blob offload.

### `job_sources`

- Query: list greenhouse|lever
- Logical unique: `id`
- RU: Two seeded rows; negligible RU.

### `match_explanations`

- Query: point read by match_id partition
- Rel: 1—1 match_runs; overflow in Blob
- RU: PK is match_id so detail pane is a single-partition point read.

### `match_runs`

- Query: user+job
- Query: user+resume
- Query: meets_threshold + completed_at
- Rel: 1—1 match_explanations; N—1 model_registry
- Logical unique: `user_id, resume_id, job_id, idempotency_key`
- RU: Idempotency unique key is a 1-RU conflict check on retry. Retain 18 months via purge, not TTL.

### `matches`

- Query: PENDING queue by user_id, status, queued_at
- Query: ai_score range
- Query: title/company/location filters
- Rel: 1—N decision_events; latest_decision_id FK
- Logical unique: `user_id, job_id, resume_id, source`
- RU: Queue page of 25 with status+queued_at composite ~3–5 RU. Cross-partition list is forbidden.

### `metrics_snapshot`

- Query: weight_config_id + window_end desc
- Query: scope_type + scope_ref
- RU: Frozen historical metrics; PK scope_ref.

### `model_params`

- Query: user_id active params
- RU: One active param set per user.

### `model_registry`

- Query: lookup model_version_id
- Query: composite scorer identity
- Logical unique: `id, ai_service+scorer_model+version+formula`
- RU: Tiny catalog; full scan is acceptable (<10 docs).

### `recommendations`

- Query: user_id + generated_at desc
- Query: weight_config_id
- Query: status
- Rel: 0—1 decision_log per user
- RU: Decision affinity: same PK as decision_log.

### `resume_parse_events`

- Query: resume_id + created_at desc
- Rel: append-only parse/edit log
- RU: PK resume_id keeps the timeline in one partition.

### `resume_variants`

- Query: user_id list
- Rel: bytes in Blob
- RU: Reuse across attempts; user partition.

### `resumes`

- Query: user_id + is_deleted + updated_at desc
- Query: processing_status
- Query: checksum_sha256
- Rel: 1—N children embedded; 1—N resume_parse_events
- Logical unique: `user_id, id`
- RU: Library list of ~20 resumes is a single partitioned query (~5 RU).

### `run_resume_selections`

- Query: point read by run_id
- Query: user_id + created_at desc
- Rel: N—1 resumes; reject if is_deleted
- Logical unique: `run_id`
- RU: Document id equals run_id so uniqueness is free.

### `schema_migrations`

- Query: point read by version id
- Logical unique: `id`
- RU: Tiny catalog of applied schema versions; one row per version.

### `settings_audit_log`

- Query: user_id + created_at desc
- Query: entity_id + created_at desc
- Rel: immutable; retained after GDPR purge of live settings
- RU: Compliance log — no TTL. History pages stay in-partition.

### `source_fetch_runs`

- Query: source_tenant_id + started_at desc
- RU: Run history is per tenant partition.

### `source_rate_limits`

- Query: source_tenant_id point read
- Query: backoff_until
- RU: Hot write path; keep documents tiny (no payload).

### `source_tenants`

- Query: source_id + tenant_key
- Logical unique: `source_id, tenant_key`
- RU: Unique tenant_key per source partition prevents duplicate boards.

### `status_events`

- Query: auto_apply_id + created_ts desc
- RU: Append-only; 18-month retention via purge job, not TTL.

### `submit_requests`

- Query: auto_apply_id + status
- Query: vendor + vendor_application_id
- Logical unique: `vendor, idempotency_key`
- RU: Unique idempotency_key per attempt partition stops duplicate submits.

### `user_match_pref_history`

- Query: user_id + created_at desc
- Rel: append-only audit of prefs
- RU: Append-only; cheap in-partition history.

### `user_match_prefs`

- Query: point read by user_id
- Rel: 1—N user_match_pref_history
- Logical unique: `user_id`
- RU: One document per user; always a point read (~1 RU).

### `user_settings`

- Query: point read by user_id
- Query: admin list updated_at desc
- Rel: 1—N email_connections; 1—N settings_audit_log
- Logical unique: `user_id`
- RU: Point read ~1 RU. Version field is optimistic concurrency, not an index.

### `users`

- Query: point read by id
- Rel: root for all user-scoped containers
- Logical unique: `id, email`
- RU: PK /id so point reads ~1 RU. Email uniqueness is enforced in the DAL (PK is not /email).

### `vendor_field_mappings`

- Query: vendor partition list
- RU: Small mapping catalog per vendor.

### `webhook_callbacks`

- Query: vendor_application_id partition
- Query: dedupe_key
- Logical unique: `vendor, vendor_application_id, dedupe_key`
- RU: TTL 90 days per Auto-Apply PRD. Unique dedupe_key drops duplicate vendor posts.

### `weight_config`

- Query: point read; is_active lookup
- Logical unique: `weight_config_id`
- RU: Catalog sized; at most one is_active=true (app-enforced).

### `weight_tuning_event`

- Query: point read by tuning_event_id
- RU: Low write volume.

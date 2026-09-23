# Cosmos DB schema

Generated from `app.storage.catalog` and the Database PRDs.
Unique-key paths omit the partition key (Cosmos unique keys are per partition).
TTL is reserved for transient scrape/ingest/webhook rows; durable history is purged by job.

| Container | Feature | Entity | Partition key | TTL (days) | Unique keys | Composites | Consistency | Owner | Retention | PII |
|---|---|---|---|---|---|---|---|---|---|---|
| `apply_packages` | auto_apply | ApplyPackage | `/auto_apply_id` | — | — | 1 | Session | apply | — | — |
| `apply_runs` | auto_apply | ApplyRun | `/userId` | 365 | /idempotency_key | 2 | Session | apply | 365 | — |
| `attachments` | schema_plane | Attachment | `/userId` | — | — | 1 | Session | platform | 730 | filename |
| `audit_events` | review | AuditEvent | `/user_id` | — | — | 3 | Session | review | 365 | — |
| `auto_apply_attempts` | auto_apply | Application | `/user_id` | 180 | /job_id+/resume_id | 6 | Session | apply | 547 | — |
| `auto_apply_rules` | schema_plane | AutoApplyRule | `/userId` | — | — | 1 | Session | platform | — | — |
| `candidates` | schema_plane | Candidate | `/id` | — | — | 1 | Session | platform | 730 | email,phone |
| `companies` | schema_plane | Company | `/id` | — | — | 1 | Session | platform | — | — |
| `cover_letters` | auto_apply | CoverLetter | `/user_id` | — | — | 1 | Session | apply | — | body |
| `crawl_schedules` | job_sources | CrawlSchedule | `/source_tenant_id` | — | — | 1 | Session | ingest | — | — |
| `data_subjects` | privacy | DataSubject | `/userId` | — | — | 0 | Session | privacy | — | — |
| `decision_events` | review | DecisionEvent | `/user_id` | — | — | 4 | Session | review | 365 | — |
| `decision_log` | learning | DecisionLog | `/user_id` | — | /recommendation_id | 2 | Session | learning | — | — |
| `email_accounts` | mail | EmailAccount | `/id` | — | — | 0 | Session | mail | — | address,smtp_address |
| `email_attachments` | mail | EmailAttachment | `/email_account_id` | — | — | 0 | Session | mail | — | — |
| `email_connections` | settings | EmailConnection | `/user_id` | — | — | 2 | Strong | settings | — | access_token_enc,refresh_token_enc,account_email |
| `email_drafts` | mail | EmailDraft | `/email_account_id` | — | — | 0 | Session | mail | — | — |
| `email_ingestion_events` | mail | EmailIngestionEvent | `/email_account_id` | 30 | — | 0 | Session | mail | 30 | — |
| `email_link_audits` | mail | EmailLinkAudit | `/email_account_id` | — | — | 0 | Session | mail | — | — |
| `email_messages` | mail | EmailMessage | `/email_account_id` | — | /graph_message_id | 6 | Session | mail | 180 | from_address,to_addresses,body_text,body_html,body,from,to |
| `email_recipients` | mail | EmailRecipient | `/email_account_id` | — | — | 0 | Session | mail | — | address |
| `email_templates` | mail | EmailTemplate | `/id` | — | — | 0 | Session | mail | — | — |
| `email_threads` | mail | MailThread | `/email_account_id` | — | /graph_conversation_id | 4 | Session | mail | 180 | — |
| `event_log` | platform | EventLog | `/user_id` | 30 | — | 2 | Session | platform | 30 | — |
| `export_bundles` | privacy | ExportBundle | `/userId` | 7 | — | 0 | Session | privacy | 7 | — |
| `fetch_cursors` | job_sources | FetchCursor | `/source_tenant_id` | — | /endpoint | 1 | Session | ingest | — | — |
| `fetch_requests` | job_sources | FetchRequest | `/source_tenant_id` | 30 | — | 3 | Session | ingest | 30 | — |
| `form_autofill_values` | auto_apply | FormAutofillValue | `/auto_apply_id` | — | /vendor+/field_key | 1 | Strong | apply | — | — |
| `graph_subscriptions` | mail | GraphSubscription | `/email_account_id` | — | — | 0 | Session | mail | — | — |
| `graph_sync_cursors` | mail | GraphSyncCursor | `/email_account_id` | — | — | 0 | Session | mail | — | — |
| `integration_outbox` | schema_plane | IntegrationOutbox | `/id` | 14 | — | 1 | Session | platform | 90 | — |
| `job_posting_links` | job_sources | JobPostingLink | `/raw_id` | — | — | 2 | Session | ingest | — | — |
| `job_postings_canonical` | job_sources | JobPosting | `/id` | — | /canonical_key; /dedupe_hash | 7 | Session | ingest | 365 | — |
| `job_postings_raw` | job_sources | JobPostingRaw | `/source_tenant_id` | 90 | — | 4 | Session | ingest | 365 | payload,text,body |
| `job_sources` | job_sources | JobSource | `/id` | — | — | 1 | Session | ingest | — | — |
| `legal_holds` | privacy | LegalHold | `/userId` | — | — | 0 | Session | privacy | — | — |
| `match_evidence` | matching | MatchEvidence | `/userId` | 180 | — | 1 | Session | matching | 365 | sentences,snippet,text |
| `match_explanations` | matching | MatchExplanation | `/match_id` | — | — | 1 | Session | matching | — | — |
| `match_records` | matching | MatchRecord | `/userId` | — | — | 2 | Session | matching | 365 | — |
| `match_runs` | matching | MatchRun | `/user_id` | — | /idempotency_key | 5 | Session | matching | 547 | — |
| `matches` | review | ReviewMatch | `/user_id` | — | /job_id+/resume_id | 14 | Session | review | 365 | — |
| `metrics_snapshot` | learning | MetricsSnapshot | `/scope_ref` | — | — | 2 | Session | learning | — | — |
| `model_params` | learning | ModelParams | `/user_id` | — | — | 1 | Session | learning | — | — |
| `model_registry` | matching | ModelRegistry | `/id` | — | — | 1 | Session | matching | — | — |
| `oauth_credentials` | schema_plane | OAuthCredential | `/userId` | — | — | 1 | Session | platform | 30 | access_token,refresh_token,secret |
| `pii_field_catalog` | privacy | PiiFieldCatalog | `/id` | — | — | 0 | Session | privacy | — | — |
| `privacy_audit_log` | privacy | PrivacyAuditLog | `/userId` | — | — | 1 | Session | privacy | — | — |
| `privacy_requests` | privacy | PrivacyRequest | `/userId` | — | — | 1 | Session | privacy | — | — |
| `recommendations` | learning | Recommendation | `/user_id` | — | — | 3 | Session | learning | — | — |
| `recruiter_inboxes` | schema_plane | RecruiterInbox | `/recruiterId` | — | — | 1 | Session | platform | — | — |
| `recruiters` | schema_plane | Recruiter | `/companyId` | — | — | 1 | Session | platform | — | email,phone |
| `resume_contacts` | resumes | ResumeContact | `/resume_id` | — | — | 0 | Session | resumes | 730 | email,phone,full_name |
| `resume_educations` | resumes | ResumeEducation | `/resume_id` | — | — | 1 | Session | resumes | 730 | — |
| `resume_experiences` | resumes | ResumeExperience | `/resume_id` | — | — | 1 | Session | resumes | 730 | — |
| `resume_parse_events` | resumes | ResumeParseEvent | `/resume_id` | 90 | — | 1 | Session | resumes | 90 | snapshot,rawJson,text |
| `resume_parse_queue` | schema_plane | ResumeParseQueue | `/userId` | 7 | — | 1 | Session | platform | 730 | — |
| `resume_skills` | resumes | ResumeSkill | `/resume_id` | — | — | 1 | Session | resumes | 730 | name |
| `resume_variants` | auto_apply | ResumeVariant | `/user_id` | — | — | 1 | Session | apply | — | — |
| `resume_versions` | resumes | ResumeVersion | `/resume_id` | — | — | 2 | Session | resumes | 730 | rawJson,text |
| `resumes` | resumes | Resume | `/user_id` | — | — | 3 | Session | resumes | 730 | original_filename,rawJson,text,text_preview |
| `retention_jobs` | privacy | RetentionJob | `/id` | 90 | — | 0 | Session | privacy | 90 | — |
| `retention_policies` | privacy | RetentionPolicy | `/id` | — | — | 0 | Session | privacy | — | — |
| `run_resume_selections` | resumes | RunResumeSelection | `/run_id` | — | — | 1 | Session | resumes | — | — |
| `schema_migrations` | platform | SchemaMigration | `/id` | — | — | 1 | Strong | platform | — | — |
| `scoring_runs` | matching | ScoringRun | `/userId` | — | /correlationId | 2 | Session | matching | — | — |
| `scrape_jobs_queue` | schema_plane | ScrapeJob | `/source` | 7 | /fingerprint | 1 | Session | platform | 7 | — |
| `settings_audit_log` | settings | SettingsAudit | `/user_id` | — | — | 2 | Session | settings | — | — |
| `source_fetch_runs` | job_sources | SourceFetchRun | `/source_tenant_id` | — | — | 1 | Session | ingest | — | — |
| `source_rate_limits` | job_sources | SourceRateLimit | `/source_tenant_id` | — | — | 2 | Session | ingest | — | — |
| `source_tenants` | job_sources | SourceTenant | `/source_id` | — | /tenant_key | 1 | Session | ingest | — | — |
| `source_toggles` | settings | SourceToggle | `/userId` | — | — | 3 | Session | settings | — | — |
| `status_events` | auto_apply | StatusEvent | `/auto_apply_id` | — | — | 1 | Session | apply | 547 | — |
| `submit_requests` | auto_apply | SubmitRequest | `/auto_apply_id` | — | /idempotency_key | 4 | Strong | apply | — | — |
| `user_match_pref_history` | matching | UserMatchPrefHistory | `/user_id` | — | — | 1 | Session | matching | — | — |
| `user_match_prefs` | matching | UserMatchPrefs | `/user_id` | — | — | 1 | Session | matching | — | — |
| `user_settings` | settings | UserSettings | `/user_id` | — | — | 2 | Strong | settings | — | token_blob |
| `users` | platform | User | `/id` | — | — | 1 | Session | platform | — | email |
| `vendor_field_mappings` | auto_apply | VendorFieldMapping | `/vendor` | — | — | 2 | Session | apply | — | — |
| `webhook_callbacks` | auto_apply | WebhookCallback | `/vendor_application_id` | 90 | /dedupe_key | 2 | Session | apply | 90 | — |
| `webhook_deliveries` | schema_plane | WebhookDelivery | `/webhookId` | 90 | — | 1 | Session | platform | 90 | — |
| `webhooks_outbound` | schema_plane | WebhookOutbound | `/id` | — | — | 1 | Session | platform | — | secret |
| `weight_config` | learning | WeightConfig | `/weight_config_id` | — | — | 1 | Session | learning | — | — |
| `weight_tuning_event` | learning | WeightTuningEvent | `/tuning_event_id` | — | — | 1 | Session | learning | — | — |

## Query patterns, RU notes, and API mapping

### `apply_packages`

- Query: auto_apply_id point/list
- RU: PK auto_apply_id colocates the frozen package.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(apply_packages)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `apply_runs`

- Query: userId + startedAt desc
- Query: userId + jobId desc
- Rel: 1—N auto_apply_attempts
- Logical unique: `userId, jobId, resumeId, modelVersion`
- RU: TTL ~365d. Composites (userId, startedAt desc) and (userId, jobId desc). Unique idempotency_key.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(apply_runs)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `attachments`

- Query: userId + kind
- Query: checksum
- Rel: b
- Rel: y
- Rel: t
- Rel: e
- Rel: s
- Rel:  
- Rel: i
- Rel: n
- Rel:  
- Rel: B
- Rel: l
- Rel: o
- Rel: b
- Rel: ;
- Rel:  
- Rel: M
- Rel: I
- Rel: M
- Rel: E
- Rel:  
- Rel: +
- Rel:  
- Rel: s
- Rel: i
- Rel: z
- Rel: e
- Rel:  
- Rel: m
- Rel: e
- Rel: t
- Rel: a
- Rel: d
- Rel: a
- Rel: t
- Rel: a
- Rel:  
- Rel: o
- Rel: n
- Rel: l
- Rel: y
- Logical unique: `userId, checksum`
- RU: PK /userId. Checksum uniqueness is DAL-enforced per user.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(attachments)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `audit_events`

- Query: match_id + occurred_at
- Query: event_type + occurred_at
- Rel: N—1 matches; UNLOCK_EXPIRED / degraded-view events
- RU: Telemetry volume is higher; composite indexes avoid scans on event_type.
- API: GET /api/v1/matches; POST /api/v1/matches/{matchId}/decision
- DAL: `CatalogRepository(audit_events)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `auto_apply_attempts`

- Query: user_id + status + updated_at
- Query: vendor + source_application_id
- Rel: 1—N packages, submits, status_events, webhooks
- Logical unique: `user_id, job_id, resume_id`
- RU: TTL 180d on attempts. Queue of in-flight attempts is a partitioned status filter ~3 RU. Unique (job_id, resume_id) per user.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(auto_apply_attempts)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `auto_apply_rules`

- Query: userId + priority + enabled
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: u
- Rel: s
- Rel: e
- Rel: r
- Rel: s
- Rel: ;
- Rel:  
- Rel: J
- Rel: S
- Rel: O
- Rel: N
- Rel:  
- Rel: c
- Rel: o
- Rel: n
- Rel: d
- Rel: i
- Rel: t
- Rel: i
- Rel: o
- Rel: n
- Rel: s
- RU: PK /userId. Small per-user rule set.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(auto_apply_rules)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `candidates`

- Query: point read by id
- Query: email uniqueness scan
- Rel: 1
- Rel: —
- Rel: N
- Rel:  
- Rel: r
- Rel: e
- Rel: s
- Rel: u
- Rel: m
- Rel: e
- Rel: s
- Rel:  
- Rel: v
- Rel: i
- Rel: a
- Rel:  
- Rel: c
- Rel: a
- Rel: n
- Rel: d
- Rel: i
- Rel: d
- Rel: a
- Rel: t
- Rel: e
- Rel: _
- Rel: i
- Rel: d
- Rel: ;
- Rel:  
- Rel: 1
- Rel: —
- Rel: N
- Rel:  
- Rel: a
- Rel: p
- Rel: p
- Rel: l
- Rel: i
- Rel: c
- Rel: a
- Rel: t
- Rel: i
- Rel: o
- Rel: n
- Rel: s
- Logical unique: `email, email_hash`
- RU: PK /id. Email uniqueness is DAL-enforced (Cosmos unique keys are per partition).
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(candidates)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `companies`

- Query: point read by id
- Query: domain uniqueness scan
- Rel: 1
- Rel: —
- Rel: N
- Rel:  
- Rel: j
- Rel: o
- Rel: b
- Rel: _
- Rel: p
- Rel: o
- Rel: s
- Rel: t
- Rel: i
- Rel: n
- Rel: g
- Rel: s
- Rel: ;
- Rel:  
- Rel: 1
- Rel: —
- Rel: N
- Rel:  
- Rel: r
- Rel: e
- Rel: c
- Rel: r
- Rel: u
- Rel: i
- Rel: t
- Rel: e
- Rel: r
- Rel: s
- Logical unique: `domain`
- RU: PK /id. Domain uniqueness is DAL-enforced.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(companies)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `cover_letters`

- Query: user_id list
- Query: userId + jobId + resumeId
- RU: Metadata + optional body. PK /user_id.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(cover_letters)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `crawl_schedules`

- Query: next_run_after where is_paused = false
- RU: Scheduler polls; composite next_run_after + is_paused avoids a full scan.
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(crawl_schedules)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `data_subjects`

- Query: point read by userId
- Logical unique: `userId`
- RU: GDPR subject record. PK /userId.
- API: GET /api/v1/privacy/requests
- DAL: `CatalogRepository(data_subjects)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `decision_events`

- Query: match_id + decided_at desc
- Query: user_id + created_at desc
- Query: user_id + job_id
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: m
- Rel: a
- Rel: t
- Rel: c
- Rel: h
- Rel: e
- Rel: s
- Rel: ;
- Rel:  
- Rel: a
- Rel: p
- Rel: p
- Rel: e
- Rel: n
- Rel: d
- Rel: -
- Rel: o
- Rel: n
- Rel: l
- Rel: y
- Rel:  
- Rel: w
- Rel: i
- Rel: t
- Rel: h
- Rel:  
- Rel: s
- Rel: u
- Rel: p
- Rel: e
- Rel: r
- Rel: s
- Rel: e
- Rel: d
- Rel: e
- Rel: s
- Rel: _
- Rel: d
- Rel: e
- Rel: c
- Rel: i
- Rel: s
- Rel: i
- Rel: o
- Rel: n
- Rel: _
- Rel: i
- Rel: d
- Rel: ;
- Rel:  
- Rel: u
- Rel: n
- Rel: i
- Rel: q
- Rel: u
- Rel: e
- Rel:  
- Rel: (
- Rel: u
- Rel: s
- Rel: e
- Rel: r
- Rel: ,
- Rel:  
- Rel: j
- Rel: o
- Rel: b
- Rel: )
- Rel:  
- Rel: i
- Rel: s
- Rel:  
- Rel: l
- Rel: o
- Rel: g
- Rel: i
- Rel: c
- Rel: a
- Rel: l
- Rel:  
- Rel: f
- Rel: o
- Rel: r
- Rel:  
- Rel: t
- Rel: h
- Rel: e
- Rel:  
- Rel: c
- Rel: u
- Rel: r
- Rel: r
- Rel: e
- Rel: n
- Rel: t
- Rel:  
- Rel: d
- Rel: e
- Rel: c
- Rel: i
- Rel: s
- Rel: i
- Rel: o
- Rel: n
- Logical unique: `user_id, job_id`
- RU: History reads stay in the user partition; cheap in-partition queries.
- API: GET /api/v1/matches; POST /api/v1/matches/{matchId}/decision
- DAL: `CatalogRepository(decision_events)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `decision_log`

- Query: user_id + decided_at desc
- Query: recommendation_id
- Logical unique: `recommendation_id, user_id`
- RU: One decision per recommendation per user via unique key.
- API: GET /api/v1/metrics
- DAL: `CatalogRepository(decision_log)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_accounts`

- Query: point read by id
- Query: list by user_id
- Logical unique: `id, user_id+provider`
- RU: Few accounts per user; point reads.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(email_accounts)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_attachments`

- Query: message_id list
- Rel: bytes in Blob; DB stores uri + metadata only
- RU: Metadata only — never index binary.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(email_attachments)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_connections`

- Query: user+provider
- Query: subscription_expires_at renewals
- Query: account_email lookup
- Rel: N—1 user_settings; tokens excluded from index
- Logical unique: `user_id, provider, status=active`
- RU: Token paths are excluded so encrypted blobs do not inflate the index.
- API: GET /api/v1/settings
- DAL: `CatalogRepository(email_connections)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_drafts`

- Query: thread or account list
- RU: Low volume.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(email_drafts)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_ingestion_events`

- Query: account + created_at desc
- RU: Transient ingest log — 30-day TTL.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(email_ingestion_events)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_link_audits`

- Query: thread + created_at
- RU: Low volume linking audit.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(email_link_audits)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_messages`

- Query: thread + received_at desc
- Query: receivedAt timeline
- Query: delivery_status
- Query: graph_message_id
- Query: bodyHash
- Logical unique: `email_account_id, graph_message_id`
- RU: Store bodyHash only — never persist raw body text. Unique graph_message_id per account.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(email_messages)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_recipients`

- Query: message_id list
- Query: email_thread_id + address
- Logical unique: `email_thread_id, address`
- RU: Kanban alias thread_participants. Dedupe (thread_id, email) is logical unique.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(email_recipients)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_templates`

- Query: point read by id
- RU: System templates; PK /id.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(email_templates)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `email_threads`

- Query: account + last_message_at desc
- Query: userId + externalThreadId
- Query: job_posting_id
- Query: application_id
- Logical unique: `email_account_id, graph_conversation_id`
- RU: Inbox pages of 25 ~5 RU with last_message_at composite. (userId, externalThreadId) lookup.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(email_threads)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `event_log`

- Query: user_id + occurred_at desc
- Query: event_type filter
- Rel: append-only; GDPR writes a delete receipt here
- RU: Append + recent-page queries. Composite keeps 25-item pages under ~5 RU.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(event_log)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `export_bundles`

- Query: userId + createdAt desc
- RU: Transient export zip metadata. Blob holds the bundle. TTL 7d.
- API: GET /api/v1/privacy/requests
- DAL: `CatalogRepository(export_bundles)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `fetch_cursors`

- Query: tenant + endpoint point read
- Logical unique: `source_tenant_id, endpoint`
- RU: One row per endpoint; always a point read.
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(fetch_cursors)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `fetch_requests`

- Query: run_id
- Query: tenant + request_ts
- Query: status_code
- RU: Transient HTTP attempts — 30-day TTL. Indexing status_code is cheap.
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(fetch_requests)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `form_autofill_values`

- Query: auto_apply_id + vendor + field_key
- Logical unique: `auto_apply_id, vendor, field_key`
- RU: Required-field completeness is an in-partition query.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(form_autofill_values)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `graph_subscriptions`

- Query: account point read
- Query: expires_at
- RU: Webhook renewal scan is tiny.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(graph_subscriptions)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `graph_sync_cursors`

- Query: account point read
- Logical unique: `email_account_id, mode`
- RU: One cursor document per mailbox.
- API: GET /api/v1/email/threads; POST /api/v1/threads/{threadId}/reply
- DAL: `CatalogRepository(graph_sync_cursors)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `integration_outbox`

- Query: status + nextRetryAt
- Query: dedupe_key point read
- Rel: 1
- Rel: —
- Rel: N
- Rel:  
- Rel: w
- Rel: e
- Rel: b
- Rel: h
- Rel: o
- Rel: o
- Rel: k
- Rel: _
- Rel: d
- Rel: e
- Rel: l
- Rel: i
- Rel: v
- Rel: e
- Rel: r
- Rel: i
- Rel: e
- Rel: s
- Rel: ;
- Rel:  
- Rel: K
- Rel: a
- Rel: n
- Rel: b
- Rel: a
- Rel: n
- Rel:  
- Rel: a
- Rel: l
- Rel: i
- Rel: a
- Rel: s
- Rel:  
- Rel: w
- Rel: e
- Rel: b
- Rel: h
- Rel: o
- Rel: o
- Rel: k
- Rel: s
- Rel: _
- Rel: o
- Rel: u
- Rel: t
- Rel: b
- Rel: o
- Rel: x
- Logical unique: `id, dedupe_key`
- RU: Document id equals dedupe_key so uniqueness is free. TTL 14d after delivery.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(integration_outbox)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `job_posting_links`

- Query: raw_id point read
- Query: canonical_id
- Logical unique: `raw_id`
- RU: PK raw_id enforces one canonical mapping per raw record.
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(job_posting_links)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `job_postings_canonical`

- Query: canonical_key
- Query: dedupe_hash
- Query: is_active
- Query: company + posted_at desc
- Query: location
- Query: source
- Query: apply_url
- Query: scraped_at
- Query: status
- Query: title
- Rel: 1—N raw via links; 1—N Application/matches; Kanban alias job_postings
- Logical unique: `canonical_key, dedupe_hash, company+apply_url`
- RU: PK /id so dedup lookups use indexed fields (~3 RU) not partition scans. Unique canonical_key + dedupe_hash per account. apply_url uniqueness is DAL-enforced.
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(job_postings_canonical)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `job_postings_raw`

- Query: tenant + source_posting_id
- Query: dedupe_hash
- Query: is_current
- Query: seen_last_at
- Rel: N—1 job_postings_canonical via job_posting_links; payload in Blob
- Logical unique: `source_tenant_id, source_posting_id, is_current=true`
- RU: TTL 90d for scrape snapshots. Unique source_posting_id is per tenant. Body is excluded via blob offload.
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(job_postings_raw)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `job_sources`

- Query: list greenhouse|lever
- Logical unique: `id`
- RU: Two seeded rows; negligible RU.
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(job_sources)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `legal_holds`

- Query: userId + status
- RU: Blocks GDPR delete while active.
- API: GET /api/v1/privacy/requests
- DAL: `CatalogRepository(legal_holds)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `match_evidence`

- Query: userId + matchId + createdAt asc
- Rel: N—1 match_records
- RU: TTL 180d. Composite (userId, matchId, createdAt asc).
- API: POST /api/v1/matches/rank; GET /api/v1/match-records; POST /api/v1/matching/prune; POST /api/v1/matching/batch-rescore
- DAL: `CatalogRepository(match_evidence)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `match_explanations`

- Query: point read by match_id partition
- Rel: 1—1 match_runs; overflow in Blob
- RU: PK is match_id so detail pane is a single-partition point read.
- API: POST /api/v1/matches/rank; GET /api/v1/match-records; POST /api/v1/matching/prune; POST /api/v1/matching/batch-rescore
- DAL: `CatalogRepository(match_explanations)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `match_records`

- Query: userId + jobId
- Query: userId + createdAt desc
- Query: latest selector by familyId
- Rel: 1—N match_evidence; current row id = hash(userId,jobId,resumeId,modelVersion)
- Logical unique: `userId, jobId, resumeId, modelVersion`
- RU: PK /userId. Composites (userId, jobId) and (userId, createdAt desc). Deterministic id + ETag upsert.
- API: POST /api/v1/matches/rank; GET /api/v1/match-records; POST /api/v1/matching/prune; POST /api/v1/matching/batch-rescore
- DAL: `CatalogRepository(match_records)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `match_runs`

- Query: user+job
- Query: user+resume
- Query: meets_threshold + completed_at
- Rel: 1—1 match_explanations; N—1 model_registry
- Logical unique: `user_id, resume_id, job_id, idempotency_key`
- RU: Idempotency unique key is a 1-RU conflict check on retry. Retain 18 months via purge, not TTL.
- API: POST /api/v1/matches/rank; GET /api/v1/match-records; POST /api/v1/matching/prune; POST /api/v1/matching/batch-rescore
- DAL: `CatalogRepository(match_runs)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `matches`

- Query: PENDING queue by user_id, status, queued_at
- Query: ai_score range
- Query: title/company/location filters
- Rel: 1—N decision_events; latest_decision_id FK
- Logical unique: `user_id, job_id, resume_id, source`
- RU: Queue page of 25 with status+queued_at composite ~3–5 RU. Cross-partition list is forbidden.
- API: GET /api/v1/matches; POST /api/v1/matches/{matchId}/decision
- DAL: `CatalogRepository(matches)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `metrics_snapshot`

- Query: weight_config_id + window_end desc
- Query: scope_type + scope_ref
- RU: Frozen historical metrics; PK scope_ref.
- API: GET /api/v1/metrics
- DAL: `CatalogRepository(metrics_snapshot)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `model_params`

- Query: user_id active params
- RU: One active param set per user.
- API: GET /api/v1/metrics
- DAL: `CatalogRepository(model_params)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `model_registry`

- Query: lookup model_version_id
- Query: composite scorer identity
- Logical unique: `id, ai_service+scorer_model+version+formula`
- RU: Tiny catalog; full scan is acceptable (<10 docs).
- API: POST /api/v1/matches/rank; GET /api/v1/match-records; POST /api/v1/matching/prune; POST /api/v1/matching/batch-rescore
- DAL: `CatalogRepository(model_registry)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `oauth_credentials`

- Query: userId + provider point read
- Rel: t
- Rel: o
- Rel: k
- Rel: e
- Rel: n
- Rel: s
- Rel:  
- Rel: e
- Rel: n
- Rel: c
- Rel: r
- Rel: y
- Rel: p
- Rel: t
- Rel: e
- Rel: d
- Rel:  
- Rel: a
- Rel: t
- Rel:  
- Rel: r
- Rel: e
- Rel: s
- Rel: t
- Rel: ;
- Rel:  
- Rel: e
- Rel: x
- Rel: c
- Rel: l
- Rel: u
- Rel: d
- Rel: e
- Rel: d
- Rel:  
- Rel: f
- Rel: r
- Rel: o
- Rel: m
- Rel:  
- Rel: i
- Rel: n
- Rel: d
- Rel: e
- Rel: x
- Logical unique: `userId, provider`
- RU: PK /userId. Token paths excluded from the index.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(oauth_credentials)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `pii_field_catalog`

- Query: container + path
- RU: Mirrors app.storage.pii MASK/ENCRYPT paths.
- API: GET /api/v1/privacy/requests
- DAL: `CatalogRepository(pii_field_catalog)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `privacy_audit_log`

- Query: userId + occurredAt desc
- RU: Append-only privacy actions.
- API: GET /api/v1/privacy/requests
- DAL: `CatalogRepository(privacy_audit_log)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `privacy_requests`

- Query: userId + createdAt desc
- RU: Access/export/delete requests. Soft-delete via status.
- API: GET /api/v1/privacy/requests
- DAL: `CatalogRepository(privacy_requests)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `recommendations`

- Query: user_id + generated_at desc
- Query: weight_config_id
- Query: status
- Rel: 0—1 decision_log per user
- RU: Decision affinity: same PK as decision_log.
- API: GET /api/v1/metrics
- DAL: `CatalogRepository(recommendations)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `recruiter_inboxes`

- Query: recruiterId + provider
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: r
- Rel: e
- Rel: c
- Rel: r
- Rel: u
- Rel: i
- Rel: t
- Rel: e
- Rel: r
- Rel: s
- Rel: ;
- Rel:  
- Rel: o
- Rel: a
- Rel: u
- Rel: t
- Rel: h
- Rel: _
- Rel: r
- Rel: e
- Rel: f
- Rel:  
- Rel: →
- Rel:  
- Rel: o
- Rel: a
- Rel: u
- Rel: t
- Rel: h
- Rel: _
- Rel: c
- Rel: r
- Rel: e
- Rel: d
- Rel: e
- Rel: n
- Rel: t
- Rel: i
- Rel: a
- Rel: l
- Rel: s
- Logical unique: `recruiterId, provider, address`
- RU: PK /recruiterId. One inbox row per provider+address.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(recruiter_inboxes)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `recruiters`

- Query: companyId + email
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: c
- Rel: o
- Rel: m
- Rel: p
- Rel: a
- Rel: n
- Rel: i
- Rel: e
- Rel: s
- Rel: ;
- Rel:  
- Rel: 1
- Rel: —
- Rel: N
- Rel:  
- Rel: r
- Rel: e
- Rel: c
- Rel: r
- Rel: u
- Rel: i
- Rel: t
- Rel: e
- Rel: r
- Rel: _
- Rel: i
- Rel: n
- Rel: b
- Rel: o
- Rel: x
- Rel: e
- Rel: s
- Logical unique: `companyId, email, email_hash`
- RU: PK /companyId colocates a company's recruiters. Email unique per company.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(recruiters)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `resume_contacts`

- Query: point read by resume_id
- Rel: 1
- Rel: —
- Rel: 1
- Rel:  
- Rel: r
- Rel: e
- Rel: s
- Rel: u
- Rel: m
- Rel: e
- Rel: s
- Rel: ;
- Rel:  
- Rel: d
- Rel: o
- Rel: c
- Rel: u
- Rel: m
- Rel: e
- Rel: n
- Rel: t
- Rel:  
- Rel: i
- Rel: d
- Rel:  
- Rel: e
- Rel: q
- Rel: u
- Rel: a
- Rel: l
- Rel: s
- Rel:  
- Rel: r
- Rel: e
- Rel: s
- Rel: u
- Rel: m
- Rel: e
- Rel: _
- Rel: i
- Rel: d
- Logical unique: `resume_id`
- RU: PK /resume_id plus id=resume_id makes the 1:1 unique without a unique-key policy.
- API: GET /api/resumes
- DAL: `CatalogRepository(resume_contacts)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `resume_educations`

- Query: resume_id + order_index
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: r
- Rel: e
- Rel: s
- Rel: u
- Rel: m
- Rel: e
- Rel: s
- Rel: ;
- Rel:  
- Rel: o
- Rel: r
- Rel: d
- Rel: e
- Rel: r
- Rel: _
- Rel: i
- Rel: n
- Rel: d
- Rel: e
- Rel: x
- Rel:  
- Rel: f
- Rel: o
- Rel: r
- Rel:  
- Rel: d
- Rel: e
- Rel: t
- Rel: e
- Rel: r
- Rel: m
- Rel: i
- Rel: n
- Rel: i
- Rel: s
- Rel: t
- Rel: i
- Rel: c
- Rel:  
- Rel: U
- Rel: I
- Rel:  
- Rel: o
- Rel: r
- Rel: d
- Rel: e
- Rel: r
- RU: In-partition list ordered by order_index is a single composite (~3 RU).
- API: GET /api/resumes
- DAL: `CatalogRepository(resume_educations)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `resume_experiences`

- Query: resume_id + order_index
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: r
- Rel: e
- Rel: s
- Rel: u
- Rel: m
- Rel: e
- Rel: s
- Rel: ;
- Rel:  
- Rel: e
- Rel: n
- Rel: d
- Rel: _
- Rel: d
- Rel: a
- Rel: t
- Rel: e
- Rel:  
- Rel: >
- Rel: =
- Rel:  
- Rel: s
- Rel: t
- Rel: a
- Rel: r
- Rel: t
- Rel: _
- Rel: d
- Rel: a
- Rel: t
- Rel: e
- Rel: ;
- Rel:  
- Rel: i
- Rel: s
- Rel: _
- Rel: c
- Rel: u
- Rel: r
- Rel: r
- Rel: e
- Rel: n
- Rel: t
- Rel:  
- Rel: i
- Rel: m
- Rel: p
- Rel: l
- Rel: i
- Rel: e
- Rel: s
- Rel:  
- Rel: e
- Rel: n
- Rel: d
- Rel: _
- Rel: d
- Rel: a
- Rel: t
- Rel: e
- Rel:  
- Rel: n
- Rel: u
- Rel: l
- Rel: l
- RU: In-partition list ordered by order_index is a single composite (~3 RU).
- API: GET /api/resumes
- DAL: `CatalogRepository(resume_experiences)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `resume_parse_events`

- Query: resume_id + created_at desc
- Query: userId + resumeId latest version
- Rel: append-only parse/edit log; Kanban alias resume_parsed
- RU: TTL 90d prunes stale parsed versions. PK resume_id keeps the timeline in one partition.
- API: GET /api/resumes
- DAL: `CatalogRepository(resume_parse_events)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `resume_parse_queue`

- Query: userId + status + createdAt desc
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: r
- Rel: e
- Rel: s
- Rel: u
- Rel: m
- Rel: e
- Rel: s
- Rel: ;
- Rel:  
- Rel: s
- Rel: t
- Rel: a
- Rel: t
- Rel: e
- Rel: s
- Rel:  
- Rel: q
- Rel: u
- Rel: e
- Rel: u
- Rel: e
- Rel: d
- Rel: |
- Rel: p
- Rel: r
- Rel: o
- Rel: c
- Rel: e
- Rel: s
- Rel: s
- Rel: i
- Rel: n
- Rel: g
- Rel: |
- Rel: d
- Rel: o
- Rel: n
- Rel: e
- Rel: |
- Rel: f
- Rel: a
- Rel: i
- Rel: l
- Rel: e
- Rel: d
- RU: TTL 7d. PK /userId keeps a user's parse jobs in one partition.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(resume_parse_queue)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `resume_skills`

- Query: resume_id + order_index
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: r
- Rel: e
- Rel: s
- Rel: u
- Rel: m
- Rel: e
- Rel: s
- Rel: ;
- Rel:  
- Rel: s
- Rel: o
- Rel: u
- Rel: r
- Rel: c
- Rel: e
- Rel:  
- Rel: p
- Rel: a
- Rel: r
- Rel: s
- Rel: e
- Rel: d
- Rel: |
- Rel: m
- Rel: a
- Rel: n
- Rel: u
- Rel: a
- Rel: l
- RU: In-partition list ordered by order_index is a single composite (~3 RU).
- API: GET /api/resumes
- DAL: `CatalogRepository(resume_skills)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `resume_variants`

- Query: user_id list
- Rel: bytes in Blob
- RU: Reuse across attempts; user partition.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(resume_variants)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `resume_versions`

- Query: resume_id + version desc
- Query: resume_id + is_deleted
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: r
- Rel: e
- Rel: s
- Rel: u
- Rel: m
- Rel: e
- Rel: s
- Rel: ;
- Rel:  
- Rel: b
- Rel: l
- Rel: o
- Rel: b
- Rel:  
- Rel: b
- Rel: y
- Rel: t
- Rel: e
- Rel: s
- Rel:  
- Rel: l
- Rel: i
- Rel: v
- Rel: e
- Rel:  
- Rel: i
- Rel: n
- Rel:  
- Rel: S
- Rel: t
- Rel: o
- Rel: r
- Rel: a
- Rel: g
- Rel: e
- Rel: ,
- Rel:  
- Rel: t
- Rel: h
- Rel: i
- Rel: s
- Rel:  
- Rel: r
- Rel: o
- Rel: w
- Rel:  
- Rel: i
- Rel: s
- Rel:  
- Rel: m
- Rel: e
- Rel: t
- Rel: a
- Rel: d
- Rel: a
- Rel: t
- Rel: a
- Logical unique: `resume_id, version`
- RU: Soft-deleted versions set document ttl=90d. Library point-in-time restore reads this container.
- API: GET /api/resumes
- DAL: `CatalogRepository(resume_versions)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `resumes`

- Query: user_id + is_deleted + updated_at desc
- Query: userId + updatedAt desc
- Query: createdAt range
- Query: processing_status
- Query: checksum_sha256
- Query: candidate_id
- Rel: 1—N resume_contacts/skills/experiences/educations; 1—N resume_parse_events; primaryFileId + parsedVersion FKs; candidate_id FK
- Logical unique: `user_id, id, checksum_sha256`
- RU: Library list of ~20 resumes is a single partitioned query (~5 RU). Dual-write userId/updatedAt for PRD lists.
- API: GET /api/resumes
- DAL: `CatalogRepository(resumes)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `retention_jobs`

- Query: status + startedAt desc
- RU: Transient purge-run receipts.
- API: GET /api/v1/privacy/requests
- DAL: `CatalogRepository(retention_jobs)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `retention_policies`

- Query: point read by id
- RU: Named retention windows.
- API: GET /api/v1/privacy/requests
- DAL: `CatalogRepository(retention_policies)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `run_resume_selections`

- Query: point read by run_id
- Query: user_id + created_at desc
- Rel: N—1 resumes; reject if is_deleted
- Logical unique: `run_id`
- RU: Document id equals run_id so uniqueness is free.
- API: GET /api/resumes
- DAL: `CatalogRepository(run_resume_selections)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `schema_migrations`

- Query: point read by version id
- Logical unique: `id`
- RU: Tiny catalog of applied schema versions; one row per version.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(schema_migrations)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `scoring_runs`

- Query: userId + startedAt desc
- Query: correlationId point read
- Rel: N—1 match_records; begin/end scoring telemetry
- Logical unique: `userId, jobId, resumeId, modelVersion, correlationId`
- RU: PK /userId. Composite (userId, startedAt desc). Unique correlationId per user.
- API: POST /api/v1/matches/rank; GET /api/v1/match-records; POST /api/v1/matching/prune; POST /api/v1/matching/batch-rescore
- DAL: `CatalogRepository(scoring_runs)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `scrape_jobs_queue`

- Query: source + scheduledAt
- Query: fingerprint
- Rel: f
- Rel: e
- Rel: e
- Rel: d
- Rel: s
- Rel:  
- Rel: s
- Rel: o
- Rel: u
- Rel: r
- Rel: c
- Rel: e
- Rel: _
- Rel: f
- Rel: e
- Rel: t
- Rel: c
- Rel: h
- Rel: _
- Rel: r
- Rel: u
- Rel: n
- Rel: s
- Logical unique: `source, fingerprint`
- RU: PK /source. Unique fingerprint per source partition. TTL 7d.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(scrape_jobs_queue)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `settings_audit_log`

- Query: user_id + created_at desc
- Query: entity_id + created_at desc
- Rel: immutable; retained after GDPR purge of live settings
- RU: Compliance log — no TTL. History pages stay in-partition.
- API: GET /api/v1/settings
- DAL: `CatalogRepository(settings_audit_log)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `source_fetch_runs`

- Query: source_tenant_id + started_at desc
- RU: Run history is per tenant partition.
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(source_fetch_runs)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `source_rate_limits`

- Query: source_tenant_id point read
- Query: backoff_until
- RU: Hot write path; keep documents tiny (no payload).
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(source_rate_limits)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `source_tenants`

- Query: source_id + tenant_key
- Logical unique: `source_id, tenant_key`
- RU: Unique tenant_key per source partition prevents duplicate boards.
- API: GET /api/v1/jobs
- DAL: `CatalogRepository(source_tenants)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `source_toggles`

- Query: point read by userId
- Query: userId + source
- Logical unique: `userId, source`
- RU: Per-user Greenhouse/Lever/auto-apply flags. Composite (userId, source) lookup.
- API: GET /api/v1/settings
- DAL: `CatalogRepository(source_toggles)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `status_events`

- Query: auto_apply_id + created_ts desc
- RU: Append-only; 18-month retention via purge job, not TTL.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(status_events)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `submit_requests`

- Query: auto_apply_id + status
- Query: vendor + vendor_application_id
- Logical unique: `vendor, idempotency_key`
- RU: Unique idempotency_key per attempt partition stops duplicate submits.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(submit_requests)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `user_match_pref_history`

- Query: user_id + created_at desc
- Rel: append-only audit of prefs
- RU: Append-only; cheap in-partition history.
- API: POST /api/v1/matches/rank; GET /api/v1/match-records; POST /api/v1/matching/prune; POST /api/v1/matching/batch-rescore
- DAL: `CatalogRepository(user_match_pref_history)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `user_match_prefs`

- Query: point read by user_id
- Rel: 1—N user_match_pref_history
- Logical unique: `user_id`
- RU: One document per user; always a point read (~1 RU).
- API: POST /api/v1/matches/rank; GET /api/v1/match-records; POST /api/v1/matching/prune; POST /api/v1/matching/batch-rescore
- DAL: `CatalogRepository(user_match_prefs)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `user_settings`

- Query: point read by user_id
- Query: admin list updated_at desc
- Query: userId equality
- Query: updatedAt range
- Rel: 1—N email_connections; 1—N settings_audit_log
- Logical unique: `user_id`
- RU: Point read ~1 RU. Version field is optimistic concurrency. Dual-write matchThreshold/timezone/quietHours.
- API: GET /api/v1/settings
- DAL: `CatalogRepository(user_settings)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `users`

- Query: point read by id
- Rel: root for all user-scoped containers
- Logical unique: `id, email`
- RU: PK /id so point reads ~1 RU. Email uniqueness is enforced in the DAL (PK is not /email).
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(users)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `vendor_field_mappings`

- Query: vendor partition list
- Query: siteKey + field
- Logical unique: `siteKey, field`
- RU: Kanban alias form_field_mappings. PK /vendor (siteKey). Upsert by siteKey+field.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(vendor_field_mappings)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `webhook_callbacks`

- Query: vendor_application_id partition
- Query: dedupe_key
- Logical unique: `vendor, vendor_application_id, dedupe_key`
- RU: TTL 90 days per Auto-Apply PRD. Unique dedupe_key drops duplicate vendor posts.
- API: GET /api/v1/auto-apply/requests; POST /api/v1/auto-apply/requests
- DAL: `CatalogRepository(webhook_callbacks)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `webhook_deliveries`

- Query: webhookId + nextRetryAt
- Rel: N
- Rel: —
- Rel: 1
- Rel:  
- Rel: w
- Rel: e
- Rel: b
- Rel: h
- Rel: o
- Rel: o
- Rel: k
- Rel: s
- Rel: _
- Rel: o
- Rel: u
- Rel: t
- Rel: b
- Rel: o
- Rel: u
- Rel: n
- Rel: d
- RU: TTL 90d. PK /webhookId colocates delivery attempts.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(webhook_deliveries)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `webhooks_outbound`

- Query: event + active
- Query: target_url
- Rel: 1
- Rel: —
- Rel: N
- Rel:  
- Rel: w
- Rel: e
- Rel: b
- Rel: h
- Rel: o
- Rel: o
- Rel: k
- Rel: _
- Rel: d
- Rel: e
- Rel: l
- Rel: i
- Rel: v
- Rel: e
- Rel: r
- Rel: i
- Rel: e
- Rel: s
- Logical unique: `target_url`
- RU: PK /id. target_url uniqueness is DAL-enforced.
- API: GET /api/v1/ops/storage
- DAL: `CatalogRepository(webhooks_outbound)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `weight_config`

- Query: point read; is_active lookup
- Logical unique: `weight_config_id`
- RU: Catalog sized; at most one is_active=true (app-enforced).
- API: GET /api/v1/metrics
- DAL: `CatalogRepository(weight_config)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

### `weight_tuning_event`

- Query: point read by tuning_event_id
- RU: Low write volume.
- API: GET /api/v1/metrics
- DAL: `CatalogRepository(weight_tuning_event)`
- SLA: p95 in-partition < 250ms; queue page of 25 ≤ 5 RU

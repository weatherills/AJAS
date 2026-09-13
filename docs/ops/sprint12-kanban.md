# Sprint 12 Kanban log

Landed on `main` as `[S12]` commits.

- [x] 001 Multi-tenant architecture: org/workspace model and data scoping
- [x] 002 Tenant onboarding flow and admin invite emails
- [x] 003 Roles & permissions: RBAC (Owner, Admin, Member, Read-only)
- [x] 004 Access control middleware and permission checks across APIs
- [x] 005 Billing: metered usage counters (ingest/match/apply/email)
- [x] 006 Billing: plan tiers (Free, Pro, Team) with feature gates
- [x] 007 Billing: Stripe subscription + metered billing integration
- [x] 008 Billing: webhook handling and invoice status sync
- [x] 009 Account limits: enforce soft/hard caps with UX messages
- [x] 010 Admin console: tenant usage dashboard and actions

## Batch 1 gate
- tests/lint/typecheck green after task 10
- [x] 011 Data export: user/tenant GDPR bundle (JSON + CSV)
- [x] 012 Data import: upload resume library (PDF, DOCX) with parsing queue
- [x] 013 Recruiter portal: limited view to share candidate matches
- [x] 014 Shareable links: expiring tokens for job/match views
- [x] 015 Feedback loop: thumbs up/down on match quality per job
- [x] 016 Feedback training: adjust weights from user feedback
- [x] 017 Ranking v3: feature store and offline training harness
- [x] 018 AB testing framework: config, randomization, metrics hook
- [x] 019 AB test: explanation style variants (bullet vs narrative)
- [x] 020 Skill graph: co-occurrence mining to expand synonyms

## Batch 2 gate
- tests/lint/typecheck green after task 20
- [x] 021 Hardening: HTML sanitizer and unsafe content guardrails
- [x] 022 PII scrubber v2: context-aware redaction in logs and payloads
- [x] 023 Secret rotation scheduler and alerting
- [x] 024 SSO: Google OAuth for teams (SAML/OIDC scaffold)
- [x] 025 Session security: device/session management UI
- [x] 026 Audit trail v2: before/after diffs for critical changes
- [x] 027 Consent management: cookie and tracking preferences
- [x] 028 Email provider integration v2: OAuth-based IMAP/SMTP
- [x] 029 Email classification v2: fine-grained labels (offer, interview, nurture)
- [x] 030 Calendar integration: parse/schedule interview invites

## Batch 3 gate
- tests/lint/typecheck green after task 30
- [x] 031 Notification digests: daily/weekly emails with key events
- [x] 032 Web push notifications setup and subscription UX
- [x] 033 Job source integrations: Greenhouse job boards adapter
- [x] 034 Job source integrations: Lever job boards adapter
- [x] 035 Company career pages: sitemap-based generic crawler
- [x] 036 Anti-bot compliance: robots.txt + rate policy per domain
- [x] 037 Proxy pool support for scraping with failover
- [x] 038 Resilience: circuit breaker around vector DB and queues
- [x] 039 Caching: result cache for hot match queries (TTL + invalidation)
- [x] 040 Performance: async batch embedding writes with backpressure

## Batch 4 gate
- tests/lint/typecheck green after task 40
- [x] 041 Performance: DB indices review and migration tuning
- [x] 042 Health dashboards: system overview page in admin
- [x] 043 Logging UI: searchable structured logs with filters
- [x] 044 Alert routing: on-call schedules and escalation policies
- [x] 045 Backup/restore: nightly backups and restore playbook
- [x] 046 Disaster recovery: RPO/RTO doc and drill checklist
- [x] 047 CI hardening: parallelize tests and cache dependencies
- [x] 048 Flaky tests: detect and quarantine framework
- [x] 049 Test coverage: raise unit coverage to 80% target
- [x] 050 Synthetic data: generators for jobs/emails/resumes

## Batch 5 gate
- tests/lint/typecheck green after task 50
- [x] 051 Red teaming: prompt/automation abuse scenarios tests
- [x] 052 Content safety: sensitive JD detection and warnings
- [x] 053 Localization: prepare keys and add fr/es base locales
- [x] 054 Date/time/number localization support in UI
- [x] 055 Accessibility v2: keyboard traps and ARIA labeling fixes
- [x] 056 Dark mode theme and toggle
- [x] 057 Mobile polish: navigation and table-to-card transforms
- [x] 058 Offline/Retry UX: queue failed actions with resume
- [x] 059 Export matches: CSV with filters and column chooser
- [x] 060 Saved searches: name, pin, and share saved filters

## Batch 6 gate
- tests/lint/typecheck green after task 60
- [x] 061 Advanced filters: regex/contains/starts-with operators
- [x] 062 Query builder UI for complex job filters
- [x] 063 Bulk apply v2: site-specific captchas/manual steps handling
- [x] 064 Cover letter library: manage and favorite templates
- [x] 065 Cover letter variables: preview and validation rules
- [x] 066 Profile completeness meter and suggestions
- [x] 067 Resume versioning: track edits and revert
- [x] 068 Multi-resume matching: pick best resume per job automatically
- [x] 069 Job change detection: notify when JD updates materially
- [x] 070 Job freshness: decay scores and stale-job cleanup

## Batch 7 gate
- tests/lint/typecheck green after task 70
- [x] 071 Duplicate company resolver: merge variants (Inc./LLC)
- [x] 072 Company insights: size, funding, tech stack enrichment
- [x] 073 Anti-spam: detect scam/spam job postings
- [x] 074 Safety: blocklist companies/keywords per tenant
- [x] 075 Rate policy UI: per-source quotas and toggles
- [x] 076 Feature flags UI: enable/disable adapters/flows
- [x] 077 Admin metrics: per-adapter success/error/latency charts

# Sprint 13 Kanban log

Landed on `main` as `[S13]` commits.

- [x] 001 Chaos testing: kill switches and failure injection
- [x] 002 Load testing: ingest and match throughput targets
- [x] 003 Canary releases: feature flag rollout process
- [x] 004 PII scanning: CI hook to detect leaks
- [x] 005 E2E suite v3: ingestion→matching→apply happy path
- [x] 006 E2E suite v3: retries and partial failure flows
- [x] 007 Fixtures v3: updated HTML snapshots per source
- [x] 008 Seed data v3: diverse resumes and roles
- [x] 009 DevEx: hot reload stability for workers
- [x] 010 DevEx: local queue emulator and scripts

## Batch 1 gate
- tests/lint/typecheck green after task 10

- [x] 011 Observability UI: trace viewer embedded
- [x] 012 Role mapping: title normalization v3
- [x] 013 Keyword alerts: saved search email triggers
- [x] 014 Security scan: dependency and SAST checks
- [x] 015 Vulnerability remediation: critical fixes
- [x] 016 UI: keyboard shortcuts for triage (accept/dismiss)
- [x] 017 UI: job change diff visualization improvements
- [x] 018 UI: match explanation inline chips with hover details
- [x] 019 UI performance: virtualized table for 10k jobs
- [x] 020 Saved searches: auto-refresh and notifications

## Batch 2 gate
- tests/lint/typecheck green after task 20

- [x] 021 LTR feature logging v2: unified schema + PII redaction
- [x] 022 Fit score calibration v2: bucket thresholds A/B test
- [x] 023 Explanations v2: evidence grouping by skill/domain
- [x] 024 Near-duplicate job collapse: per-company rollup in results
- [x] 025 Matching boosts v2: recent-role weighting curve
- [x] 026 Matching features: visa/work-authorization rule updates
- [x] 027 Matching features: seniority ladder calibration data
- [x] 028 Vector store: HNSW parameter tuning and benchmarks
- [x] 029 Embeddings pipeline: shard-aware reindex and backpressure
- [x] 030 Skills taxonomy v3: auto-extend from corpus with review queue

## Batch 3 gate
- tests/lint/typecheck green after task 30

- [x] 031 Resume parser v3: gap detection and annotation
- [x] 032 Resume parser v3: achievements metric detection (%, $, #)
- [x] 033 JD cleaner v3: boilerplate classifier using heuristics+ML
- [x] 034 Location geocoding v2: suburb/metro rollups and radius
- [x] 035 Currency support: FX normalization and display rules
- [x] 036 Salary parsing v3: equity + bonus components
- [x] 037 Normalization v3: onsite/hybrid/remote detection improvements
- [x] 038 Normalization v3: job type taxonomy (FT/PT/Contract/Intern)
- [x] 039 Crawl frontier: adaptive scheduling using success/error rates
- [x] 040 Ingestion adapters v3: Wellfound session refresh guard

## Batch 4 gate
- tests/lint/typecheck green after task 40

- [x] 041 Ingestion adapters v3: Glassdoor block detection and cool-down
- [x] 042 Ingestion adapters v3: Indeed HTML/JSON dual-path parser
- [x] 043 Ingestion adapters v3: LinkedIn resilience + captcha fallback
- [x] 044 Observability: structured tracing context propagation
- [x] 045 Privacy: field-level redaction config UI
- [x] 046 Data retention v2: per-tenant retention policies
- [x] 047 Outbound allowlist v2: per-environment gates
- [x] 048 Idempotency v3: conflict resolution strategies
- [x] 049 Error taxonomy v3: mapping to remediation playbooks
- [x] 050 Quotas v2: per-tenant/source daily and burst caps

## Batch 5 gate
- tests/lint/typecheck green after task 50


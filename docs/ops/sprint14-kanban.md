# Sprint 14 Kanban log

Landed on `main` as `[S14]` commits. CodeSpring updated after every task.

- [x] 001 ZipRecruiter adapter v1 (pagination/backoff)
- [x] 002 Monster adapter v1 (HTML + API hybrid)
- [x] 003 Hired adapter v1 with auth/session
- [x] 004 RemoteOK adapter v1
- [x] 005 Remotive adapter v1
- [x] 006 WeWorkRemotely adapter v1
- [x] 007 Workable adapter v1
- [x] 008 Greenhouse company board crawler
- [x] 009 Lever company board crawler
- [x] 010 Ashby company board crawler

## Batch 1 gate
- tests/lint/typecheck green after task 10

- [x] 011 Source adapter: bot challenge auto-detect + fallback
- [x] 012 Source adapter: rotating proxies abstraction + health
- [x] 013 Source adapter: robots.txt/crawl-delay compliance toggle
- [x] 014 Source adapter: centralized backoff + jitter policy
- [x] 015 Source adapter: HTTP fingerprint randomization
- [x] 016 Normalization: contract types (FT/PT/Contract/Intern)
- [x] 017 Normalization: benefits parsing (visa, relocation, equity)
- [x] 018 Normalization: skills canonicalization v3
- [x] 019 Normalization: title cleaning rules v3
- [x] 020 Normalization: currency normalization + TCC note

## Batch 2 gate
- tests/lint/typecheck green after task 20

- [x] 021 Geocoding: city/state/country → lat/lon cache
- [x] 022 Company domain resolver via DNS/MX/WHOIS fallback
- [x] 023 JD cleaner v3: section heuristics + bullets
- [x] 024 Salary parsing v3: multi-currency + bands
- [x] 025 Skill extractor v3: phrase chunker + negation
- [x] 026 Resume parser v3: impact bullets + scoring
- [x] 027 Embeddings: incremental reindex sweeper + retries
- [x] 028 Vector store: compaction/tombstone vacuum job v2
- [x] 029 Matching: recency/time-decay factor v2
- [x] 030 Matching: dedupe near-identical roles per company v2

## Batch 3 gate
- tests/lint/typecheck green after task 30

- [x] 031 Matching: multilingual JD support (detect + translate)
- [x] 032 Ranking: feedback logging for LTR (click/open/reply)
- [x] 033 Ranking: pairwise training data generator
- [x] 034 Ranking: calibration monitor dashboard v2
- [x] 035 Explanations: counterfactual suggestions
- [x] 036 Explanations: highlight missing must-have skills
- [x] 037 Fit score: per-dimension sub-scores UI
- [x] 038 Filters: saved presets per user
- [x] 039 Search: keyword across normalized JD fields
- [x] 040 Job list perf: windowed list + skeletons

## Batch 4 gate
- tests/lint/typecheck green after task 40

- [x] 041 Job detail: JD version diff view
- [x] 042 Bulk actions: bulk-dismiss + undo snackbar
- [x] 043 Apply: per-site field mapping overrides
- [x] 044 Cover letters: tone/style presets
- [x] 045 Attachment manager: multi-resume profiles
- [x] 046 Email: IMAP labels mapping to internal states
- [x] 047 Email: sender reputation guard (daily cap + warmup)
- [x] 048 Replies: variable placeholders + preview v2
- [x] 049 Follow-ups: auto-reminders at 24/72h
- [x] 050 Notification center: in-app toasts + digest email

## Batch 5 gate
- tests/lint/typecheck green after task 50

- [x] 051 Audit trail UI: filter/export CSV
- [x] 052 Error taxonomy v3: codes→remediation hints
- [x] 053 Observability: trace IDs across ingest→apply
- [x] 054 Metrics dashboards: app charts page
- [x] 055 Alerts tuning: adaptive thresholds
- [x] 056 Privacy: on-demand data export (GDPR bundle)
- [x] 057 Privacy: right-to-be-forgotten purge job + UI
- [x] 058 Security: outbound domain allowlist UI + policy
- [x] 059 Secrets rotation: hot-reload for adapters
- [x] 060 Rate limit policy v2: per-tenant + endpoint

## Batch 6 gate
- tests/lint/typecheck green after task 60

- [x] 061 Idempotency keys v2: persistence window logs
- [x] 062 Queue health: stuck-job detector + auto-requeue
- [x] 063 Dead-letter queue UI: inspect/retry with redaction
- [x] 064 Backfill: re-normalize historical jobs
- [x] 065 CLI: verify adapters + dry-run single source
- [x] 066 E2E: ingestion→ranking→explain regressions
- [x] 067 E2E: email parser templates coverage
- [x] 068 Unit tests: salary/geo/negation edge cases v2
- [x] 069 Fixtures: real-world HTML snapshots expansion
- [x] 070 Seed data v3: resumes by seniority/remote

## Batch 7 gate
- tests/lint/typecheck green after task 70

- [x] 071 API: pagination/sorting on jobs/matches
- [x] 072 API auth: scoped tokens for automation tasks
- [x] 073 Webhooks: ingestion/apply events + signatures
- [x] 074 Health endpoints v2: dependency matrix + version
- [x] 075 Performance: cache hot queries with TTL
- [x] 076 Performance: batch DB writes (ingestion/logs)
- [x] 077 Accessibility: WCAG audit fixes (list/detail/filter)
- [x] 078 I18N: prepare strings + base locale (en)

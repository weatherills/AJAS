# Sprint 16 Kanban log

Landed as `[S16]` commits. CodeSpring updated after every task when the CLI is reachable.

- [x] 001 BuiltIn adapter v1 (pagination/backoff)
- [x] 002 Handshake adapter v1
- [x] 003 USAJobs adapter v1
- [x] 004 The Muse adapter v1
- [x] 005 SmartRecruiters adapter v1
- [x] 006 Jobvite adapter v1
- [x] 007 Recruitee adapter v1
- [x] 008 TeamTailor adapter v1
- [x] 009 JazzHR adapter v1
- [x] 010 Workday company board crawler v2

## Batch 1 gate
- tests/lint/typecheck green after task 10

- [x] 011 Source adapter: HTTP/2 vs HTTP/1.1 fallback
- [x] 012 Source adapter: certificate pinning store
- [x] 013 Source adapter: 304 Not Modified short-circuit
- [x] 014 Source adapter: JSON-LD JobPosting parser
- [x] 015 Source adapter: htmx/infinite-scroll fixture pager
- [x] 016 Source adapter: per-tenant robots cache
- [x] 017 Source adapter: crawl budget remaining gauge
- [x] 018 Source adapter: consent banner fail-closed v3
- [x] 019 Source adapter: AMP vs canonical URL picker
- [x] 020 Source adapter: Last-Modified If-Modified-Since

## Batch 2 gate
- tests/lint/typecheck green after task 20

- [x] 021 Normalization: employment type v3
- [x] 022 Normalization: work authorization v2
- [x] 023 Normalization: degree aliases
- [x] 024 Normalization: clearance levels
- [x] 025 Normalization: industry NAICS map
- [x] 026 JD cleaner v5: responsibilities vs qualifications
- [x] 027 Salary parsing v5: hourly overtime + equity
- [x] 028 Skill extractor v5: cert vs tool split
- [x] 029 Resume parser v5: date overlap repair
- [x] 030 Company brand graph (DBA / trade names)

## Batch 3 gate
- tests/lint/typecheck green after task 30

- [x] 031 Embeddings: content-hash skip v2
- [x] 032 Vector store: replica health probe
- [x] 033 Matching: commute-time proxy
- [x] 034 Matching: title-family clustering v2
- [x] 035 Matching: equity-band overlap
- [x] 036 Ranking: listwise LTR features v3
- [x] 037 Ranking: thompson sampling explore
- [x] 038 Explanations: why-this-and-not-that
- [x] 039 Fit score: prediction interval
- [x] 040 Diversity: de-bias company tokens

## Batch 4 gate
- tests/lint/typecheck green after task 40

- [x] 041 Filters: org-shared presets v2
- [x] 042 Search: phrase + NOT operator
- [x] 043 Job list: density compact mode
- [x] 044 Job detail: hiring-team panel
- [x] 045 Bulk actions: bulk-archive + undo
- [x] 046 Apply: optional-field warnings
- [x] 047 Cover letters: reading-level target
- [x] 048 Attachment manager: file-hash dedupe
- [x] 049 Compare: three-way match table
- [x] 050 Saved searches: webhook notify

## Batch 5 gate
- tests/lint/typecheck green after task 50

- [x] 051 Email: In-Reply-To thread merge
- [x] 052 Email: auto-reply detector
- [x] 053 Replies: timezone-safe calendar placeholder
- [x] 054 Follow-ups: skip if meeting booked
- [x] 055 Notification: weekend quiet hours
- [x] 056 Notification: digest vs instant
- [x] 057 Inbox: ATS vs human split v2
- [x] 058 Templates: A/B body variants
- [x] 059 Signatures: legal disclaimer block
- [x] 060 Unsubscribe/List-Unsubscribe honor

## Batch 6 gate
- tests/lint/typecheck green after task 60

- [ ] 061 Audit: break-glass access trail
- [ ] 062 Error taxonomy v5: user vs operator vs vendor
- [ ] 063 Observability: USE metrics pack
- [ ] 064 Metrics: error-budget remaining
- [ ] 065 Privacy: DSAR export encryption
- [ ] 066 Security: HSTS + CSP enforce toggle
- [ ] 067 Secrets: three-key rotation window
- [ ] 068 Rate limit: token bucket v3
- [ ] 069 Idempotency: replay storm detector
- [ ] 070 Queue: poison-message replay cap

## Batch 7 gate
- tests/lint/typecheck green after task 70

- [ ] 071 Backfill: brand alias merge
- [ ] 072 CLI: smoke one board fixture v2
- [ ] 073 E2E: apply dry-run regressions v2
- [ ] 074 Unit tests: clearance/degree edge cases
- [ ] 075 Fixtures: s16 HTML/JSON snapshots
- [ ] 076 Seed data v5: mixed locale users
- [ ] 077 API: cursor pagination v3
- [ ] 078 API: webhook subscription filters
- [ ] 079 Health: build SHA + dependency matrix v5
- [ ] 080 Performance: request coalescing v2

## Batch 8 gate
- tests/lint/typecheck green after task 80

- [ ] 081 Accessibility: skip-link pack
- [ ] 082 I18N: currency/date formats v2
- [ ] 083 Mobile: swipe actions
- [ ] 084 Docs: Sprint 16 operations guide
- [ ] 085 Docs: API examples v4
- [ ] 086 Docs: observability how-to v4
- [ ] 087 Docs: data model v3
- [ ] 088 Docs: rollback steps v4
- [ ] 089 Data: index migration v4
- [ ] 090 Data: salary FX backfill v4

## Batch 9 gate
- tests/lint/typecheck green after task 90

- [ ] 091 Data: vector store compaction v5
- [ ] 092 Data: retention sweep v5
- [ ] 093 Maintenance: dependency audit v3
- [ ] 094 Maintenance: lint and type alignment v3
- [ ] 095 Maintenance: unused adapter flags stay off
- [ ] 096 CLI: reindex by tenant v2
- [ ] 097 Webhooks: adapter outcome retries v2
- [ ] 098 Health: synthetic probe pack v2
- [ ] 099 Idempotency: conflict export JSON
- [ ] 100 Feature flags: percentage rollout + audit v2

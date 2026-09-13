# Sprint 10 batch hardening

Automated gate after every 10 Sprint 10 tasks: backend pytest, frontend vitest, `tsc --noEmit`, and oxlint.

## Batch 1 (tasks 1–10)

- Backend: 493 passed
- Frontend: 98 passed
- Typecheck: clean
- Lint: existing warnings only (no new errors)

Covered: Glassdoor/Wellfound fixture adapters, rotating UAs + jitter, circuit breaker, domain/MX/WHOIS resolver, geocode cache, JD cleaner v2, salary v2, skill extractor v2, resume impact scoring.

## Batch 2 (tasks 11–20)

- Backend: 499 passed
- Frontend: 100 passed
- Typecheck: clean
- Lint: fixed duplicate `saveFilters` import in JobFeed; remaining warnings pre-existed

Covered: embedding reindex sweeper, vector vacuum, recency boost, fairness dedupe, isotonic calibration, explanation token spans, fit-bucket colors/tooltips, filter presets, JD keyword search, windowed list + skeletons.

## Batch 3 (tasks 21–30)

- Backend: 508 passed
- Frontend: 104 passed
- Typecheck: clean
- Lint: fixed Ops.tsx notification section markup; remaining warnings pre-existed

Covered: JD version diff, bulk-dismiss undo snackbar, apply field maps, cover-letter tones, tagged resume profiles, IMAP label mapping, sender warm-up, reply template placeholders, 24/72h SLA, notification digest.

## Batch 4 (tasks 31–40)

- Backend: 518 passed
- Frontend: 108 passed
- Typecheck: clean
- Lint: restored Settings `userId` state dropped during allowlist UI; remaining warnings pre-existed

Covered: audit CSV UI, error taxonomy v2, pipeline traces, metrics charts, adaptive alerts, GDPR export/purge, outbound allowlist policy UI, secrets hot-reload, per-tenant rate limits.

## Batch 5 (tasks 41–50)

- Backend: 528 passed
- Frontend: 110 passed
- Typecheck: clean
- Lint: existing warnings only

Covered: idempotency window/conflicts, stuck-queue requeue, DLQ redaction UI, job backfill, adapter dry-run CLI, ingestion→rank→explain E2E, email parser templates, salary/geo/negation edges, HTML adapter snapshots, junior/mid/senior/remote seeds.

## Batch 6 (tasks 51–60)

- Backend: 534 passed
- Frontend: 112 passed
- Typecheck: clean
- Lint: existing warnings only (no new errors)

Covered: jobs/matches pagination+sort helper, scoped automation tokens, webhook HMAC, health v2 dependency matrix, query TTL cache, batch DB writes, WCAG skip-link/filter expanded, English i18n + locale switch, phone layout for core views, Sprint 10 ops/troubleshooting guide.

## Batch 7 (planned backlog remainder)

- Backend: 564 passed
- Frontend: 115 passed
- Typecheck: clean
- Lint: existing warnings only

Covered remaining `[Sprint 10]` Kanban: Workday/ZipRecruiter fixture adapters, proxy pool, CAPTCHA HITL, listing drift, DPIA/robots doc, resume certs/education/timeline/i18n, matching radius/visa/rerank/A-B/active-learning/feedback, Graph OAuth/Outlook/threading, PII review, owner RBAC, retention executor, pipeline SLOs, Slack payloads, quotas, Cosmos index policy, model budgets, Settings flag/limits UI.

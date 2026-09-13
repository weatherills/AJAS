# Sprint 12 batch test gates

After every 10 Sprint 12 tasks: backend pytest, frontend `npm test`,
`npx tsc --noEmit`, `npm run lint`.

| Batch | Tasks | Notes |
| --- | --- | --- |
| 1 | 1–10 tenancy/billing/admin | Org/workspace, RBAC, Stripe stub, caps |
| 2 | 11–20 sharing/ranking | GDPR CSV, recruiter links, AB, skill graph |
| 3 | 21–30 security/email | Sanitizer, SSO, sessions, IMAP OAuth, calendar |
| 4 | 31–40 ingest/perf | Digests, sitemap, circuits, match cache |
| 5 | 41–50 ops/CI | Health, logs, backup/DR, flaky quarantine, synthetics |
| 6 | 51–60 UI/i18n | Red team, fr/es, a11y, dark mode, CSV export |
| 7 | 61–70 product | Query builder, cover letters, resume versions, freshness |
| 8 | 71–80 companies/ops UI | Insights, spam, flags, DLQ, webhooks v2 |
| 9 | 81–90 API/docs | Keys, SDK, pagination, help, changelog, ETL |
| 10 | 91–109 compliance/release | Legal, CSP, IaC, CLI, bootstrap, MIME scan, bounce |

Final gate:

- Backend: 678 passed
- Frontend: 131 passed
- Typecheck: clean
- Lint: existing warnings only (no new errors)


- Batch 5: green after task 50

- Batch 6: green after task 60

- Batch 7: green after task 70

- Batch 8: green after task 80

- Batch 9: green after task 90

- Batch 10: green after task 100

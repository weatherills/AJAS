# Sprint 15 batch test gates

After every 10 Sprint 15 tasks: backend pytest, frontend `npm test`,
`npx tsc --noEmit`, `npm run lint`.

| Batch | Tasks | Notes |
| --- | --- | --- |
| 1 | 1–10 adapters | Indeed through CareerBuilder, flags off |
| 2 | 11–20 policy | TLS, cookies, sitemap/RSS, consent fail-closed |
| 3 | 21–30 normalize | Seniority/remote, JD/salary v4, aliases |
| 4 | 31–40 matching | Checksums, location, LTR, why-not |
| 5 | 41–50 product | Boolean search, bulk-save, compare |
| 6 | 51–60 mail | Threads, quiet hours, suppression |
| 7 | 61–70 ops | DSAR, CSP, replay detector, poison queue |
| 8 | 71–80 API/perf | Cursor pagination, health v4, coalescing |
| 9 | 81–90 docs/data | Ops guide, rollback, FX backfill |
| 10 | 91–100 maintenance | Compaction, flags, wrap-up gate |

Final gate after task 100.

- Batch 1 after task 10
- Backend: 889 passed in 2.03s
- Frontend:       Tests  137 passed (137)
- Typecheck: clean
- Lint: existing warnings only


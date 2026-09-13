# Sprint 13 batch test gates

After every 10 Sprint 13 tasks: backend pytest, frontend `npm test`,
`npx tsc --noEmit`, `npm run lint`.

| Batch | Tasks | Notes |
| --- | --- | --- |
| 1 | 1–10 chaos/load/e2e/devex | Kill switches, canary, fixtures, local queues |
| 2 | 11–20 traces/UI | Trace viewer, shortcuts, chips, virtual table |
| 3 | 21–30 matching | LTR v2, collapse, visa, HNSW, taxonomy |
| 4 | 31–40 parse/ingest | Gaps, salary/FX, frontier, Wellfound guard |
| 5 | 41–50 adapters/privacy | Glassdoor/Indeed/LinkedIn, redaction, quotas |
| 6 | 51–62 ops/docs | Jitter, drain, mobile nav, adapter guide, cookbook |

Final gate after task 62.

- Batch 1 after task 10
- Backend: 728 passed in 1.88s
- Frontend:       Tests  130 passed (130)
- Typecheck: clean
- Lint: existing warnings only


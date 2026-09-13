# Sprint 14 batch test gates

After every 10 Sprint 14 tasks: backend pytest, frontend `npm test`,
`npx tsc --noEmit`, `npm run lint`.

| Batch | Tasks | Notes |
| --- | --- | --- |
| 1 | 1–10 adapters | ZipRecruiter through Ashby, flags off |
| 2 | 11–20 policy/normalize | Bot/proxy/robots, contract/benefits/skills |
| 3 | 21–30 geo/matching | Domain, JD/salary, reindex, recency |
| 4 | 31–40 ranking/UI | LTR, counterfactuals, search, windowing |
| 5 | 41–50 apply/mail | Diff, bulk dismiss, IMAP, notifications |
| 6 | 51–60 ops/privacy | Audit, traces, GDPR, allowlist, rates |
| 7 | 61–70 queues/tests | DLQ, E2E, fixtures, seed |
| 8 | 71–80 API/docs | Pagination, webhooks, a11y, ops guide |
| 9 | 81–90 docs/data | Cookbook, rollback, compaction, lint |
| 10 | 91–99 maintenance | Dead flags, CLI, health v3, remote flags |

Final gate after task 99.

- Batch 1 after task 10
- Backend: 790 passed in 1.90s
- Frontend:       Tests  135 passed (135)
- Typecheck: clean
- Lint: existing warnings only

- Batch 2 after task 20
- Backend: 800 passed in 2.25s
- Frontend:       Tests  135 passed (135)
- Typecheck: clean
- Lint: existing warnings only

- Batch 3 after task 30
- Backend: 810 passed in 1.91s
- Frontend:       Tests  135 passed (135)
- Typecheck: clean
- Lint: existing warnings only

- Batch 4 after task 40
- Backend: 820 passed in 1.95s
- Frontend:       Tests  137 passed (137)
- Typecheck: clean
- Lint: existing warnings only


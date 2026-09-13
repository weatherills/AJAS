# Sprint 13 operations

Sprint 13 hardens matching, ingest adapters, observability, and operator
product surfaces on top of Sprint 12. Optional adapters and live HTML
scraping stay **off**. LinkedIn captcha paths never bypass the fixture
fallback.

Batch gates: [sprint13-batches.md](./sprint13-batches.md).

## Platform

- Chaos kill switches and fail-closed injection (`app.sprint13.platform`).
- Load report against ingest/match QPS targets (20 / 50).
- Canary flag rollout with sticky percent buckets.
- E2E harness: ingest → match → apply happy path plus retry/partial failure.

## Matching and parse

- LTR v2 logs with PII redaction (`ajas.ltr.v2`).
- Fit-score A/B buckets, evidence grouping, per-company duplicate collapse.
- Visa/work-authorization gates, seniority ladder, HNSW tune, shard reindex.
- Resume gap notes, achievement metrics, JD boilerplate, FX, salary equity/bonus.
- Title, work-mode, and job-type taxonomy v3.

## Ingest

- Adaptive crawl frontier from success/error rates.
- Wellfound session refresh guard, Glassdoor 403 cooldown (circuit stays 5xx-only).
- Indeed JSON+HTML dual-path parser (fixtures only).
- LinkedIn captcha → fixture fallback, `bypass` always false.

## Ops and privacy

- Trace context propagation and embedded viewer payload.
- Per-tenant retention (≥ 7 days), field redaction, env allowlist gates.
- Idempotency v3 stored-wins / incoming-wins.
- Quotas with daily and burst caps, jittered backoff, graceful drain.
- Audit export CSV/JSON, orphan sweeper, chunked backfill.

## UI

- Accept/dismiss triage shortcuts (a/Enter + d).
- JD diff line highlighting, match explanation chips with hover details.
- Virtualized job window for 10k rows.
- Field-level redaction checkboxes in Settings.
- Mobile bottom nav with swipe between primary tabs.

## HTTP

| Route | Purpose |
| --- | --- |
| `GET /api/v1/s13/status` | Sprint version + completed count |
| `GET/POST /api/v1/s13/kill` | Kill switch / failure injection |
| `POST /api/v1/s13/canary` | Feature-flag percent rollout |
| `GET /api/v1/s13/e2e` | Happy or retry harness (`?mode=retry`) |
| `GET /api/v1/s13/traces` | Trace viewer payload |
| `GET /api/v1/s13/audit` | Audit bundle (`?format=csv`) |
| `POST /api/v1/s13/redact` | Field-level redaction |
| `GET /api/v1/s13/search` | Consistent search/sort/filter |

Health `version` is `sprint13`.

## CLI

```
python scripts/s13_queue_emulator.py enqueue --queue ingest --payload '{"id":"j1"}'
python scripts/s13_pii_scan.py backend/app
python scripts/ajas.py seed
```

Adapter authoring: [sprint13-adapter-guide.md](./sprint13-adapter-guide.md).
API examples: [sprint13-api-cookbook.md](./sprint13-api-cookbook.md).

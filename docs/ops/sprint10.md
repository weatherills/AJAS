# Sprint 10 operations guide

Sprint 10 hardens ingestion, matching, privacy, queues, and operator UX on top of
Sprint 9. **Glassdoor and Wellfound stay fixture-only.** Flags default **off**.
Live HTML scraping of those boards is not implemented; robots/consent fail closed.

See also: [adapters-and-queues.md](./adapters-and-queues.md),
[sprint9-migration.md](./sprint9-migration.md), [production.md](./production.md).
Batch test gates: [sprint10-batches.md](./sprint10-batches.md).

## Flags

| Setting | Default | Purpose |
| --- | --- | --- |
| `FLAG_GLASSDOOR_ADAPTER` | false | Load Glassdoor JSON/HTML **fixtures** (pagination + backoff in-process) |
| `FLAG_WELLFOUND_ADAPTER` | false | Load Wellfound fixtures; auth helper is a stub, not a live login |
| `FLAG_SITE_POLICY_CONSENT` | false | Required before any optional-board HTTP |
| `FLAG_RESPECT_ROBOTS` | true | Fail closed on robots.txt |
| `FLAG_INDEED_ADAPTER` | false | Indeed fixtures (Sprint 9) |
| `FLAG_LINKEDIN_ADAPTER` | false | LinkedIn fixtures (Sprint 9) |
| `FLAG_IMAP_TRANSPORT` | false | IMAP remains unimplemented |
| `FLAG_BULK_AUTO_APPLY` | false | Bulk apply still confirms per job |

Optional boards also need an allowlisted host and a closed circuit breaker.

## Adapter dry-run CLI

From the repo root (Python path includes `backend/`):

```
python scripts/verify_adapters.py glassdoor
python scripts/verify_adapters.py wellfound
python scripts/verify_adapters.py indeed --fixture backend/tests/fixtures/job_boards/indeed.json
```

The command prints JSON: fixture path, job count, feature flags, and circuit
snapshot. It never hits Glassdoor/Wellfound over the network.

HTML snapshots under `backend/tests/fixtures/job_boards/*.html` are **reference
only**; parsers read the JSON fixtures.

## Circuit breaker

`app.job_sources.circuit` opens a source after **5** consecutive 5xx-class
failures for **300 seconds**. While open, `load_fixture_jobs` returns `[]`.
Reset in-process with `circuit.reset("glassdoor")` (or `reset()` for all).

User-agent rotation and retry jitter live in `app.job_sources.http_policy`.

## Matching and ranking

- Recency: additive time-decay when `posted_at` / `postedAt` is present.
- Fairness: near-duplicate titles at the same company are de-duplicated.
- Explanations: reason codes plus token `spans` on match payloads.
- Calibration: isotonic regression scaffold with a holdout split
  (`app.matching.isotonic`). Not a production model.

Reindex sweeper / vector vacuum: `app.matching.reindex` and `app.matching.vectors`.
Historical JD re-normalize: `app.job_sources.backfill`.

## Privacy (GDPR)

Settings → **Download my data** builds `ajas.gdpr.v1` (jobs, emails, matches).
**Forget my account** runs the in-browser purge planner (`purge_plan` /
`apply_purge`). This is the product hook; Cosmos hard-delete still follows
`FLAG_DATA_RETENTION_PURGE` / retention jobs from Sprint 9.

## Queues, DLQ, idempotency

- Stuck-job detector: `app.queue_health` (age threshold → auto-requeue).
- Dead letters: Ops DLQ panel uses `app.dlq` with secret redaction.
- Idempotency v2: persistence window + conflict log (`app.idempotency_v2`).
- Rate limits v2: per-tenant and per-endpoint counters (`app.ratelimit_v2`).

## Health v2

`GET /api/health` and `GET /api/ready` now include:

- `version`: `"sprint10"`
- `dependencyMatrix`: cosmos / openai / graph / keyVault plus worker map
- existing `workers`, `dependencies`, `flags`, `imap`

## Webhooks and automation tokens

Ingestion/apply webhook HMAC: `app.webhooks_sig`. Bounce webhook still uses
`MAIL_BOUNCE_WEBHOOK_SECRET` (see production.md).

Scoped automation tokens: `app.automation_tokens` (task-scoped, not a full IdP).

## Frontend operators

- Filter presets and keyword search over normalized JD fields (Job feed).
- Fit-score color buckets + tooltips.
- Bulk dismiss + undo snackbar.
- Locale switch: English catalog only (`ajas.locale` in `localStorage`).
- Phone layout: ≤640px stacks header/nav/filters; job drawer is full viewport.
- Ops: metrics bars, audit CSV export, notification digest preview, DLQ retry.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Glassdoor/Wellfound returns no jobs | Flags off (expected). Enable `FLAG_*` **and** `FLAG_SITE_POLICY_CONSENT` in tests only. Circuit may be open after 5xx. |
| `can_fetch` false | Robots/consent fail closed, or host not on outbound allowlist (Settings). |
| CLI `count: 0` | Fixture missing, flag off, or circuit open. Pass `--fixture` explicitly. |
| Match scores unchanged after recency work | Job has no `posted_at`. Decay is additive only when that field exists. |
| Health `storage: memory` | `COSMOS_CONNECTION_STRING` unset. |
| Health `imapConfigured: false` | IMAP is a stub; Graph is the mail transport. |
| GDPR download empty | Bundle is built from in-memory/demo rows for that `userId`. |
| DLQ retry no-ops | Payload redacted; inspect remaining fields and requeue from Ops. |
| Locale switch does nothing | Only `en` exists. Unknown values fall back to English. |
| Filter presets vanish in tests | Helpers fall back to memory when `localStorage` is missing. |
| 429 from APIs | Rate-limit v2 counters per tenant/endpoint; wait or reset process. |
| Duplicate apply | Idempotency window still holds the first key; check conflict logs. |
| Stuck queue | `queue_health` should requeue aged items; otherwise inspect DLQ. |

## Rollback

Unset `FLAG_GLASSDOOR_ADAPTER` and `FLAG_WELLFOUND_ADAPTER`. Leave Greenhouse
and Lever as the production sources. Clients ignore unknown JSON fields
(`spans`, `version`, `dependencyMatrix`).

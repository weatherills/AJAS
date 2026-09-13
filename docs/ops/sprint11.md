# Sprint 11 operations

Sprint 11 extends fixture-only ingestion, matching, apply, email, and operator
tooling. **Live HTML scraping of non-Greenhouse/Lever boards is still out of
the Job Source PRD.** Optional adapters default **off**. CAPTCHA always routes
to `needs_manual`.

Batch gates: [sprint11-batches.md](./sprint11-batches.md).

## Flags (new or reused)

| Setting | Default | Purpose |
| --- | --- | --- |
| `FLAG_ZIPRECRUITER_ADAPTER` | false | ZipRecruiter JSON fixtures with cursor pages + Retry-After |
| `FLAG_HIRED_ADAPTER` | false | Hired fixtures; token required; CAPTCHA → empty + needs_manual |
| `FLAG_GREENHOUSE_CAREER_ADAPTER` | false | Parse Greenhouse career-page **HTML fixtures** |
| `FLAG_LEVER_CAREER_ADAPTER` | false | Parse Lever career-page **HTML fixtures** |
| `FLAG_WORKDAY_ADAPTER` | false | Workday JSON **and** career-page HTML fixtures |

## Ingestion

- ZipRecruiter: `app.job_sources.ziprecruiter` (cursor `pages[].next`, Retry-After).
- Hired: `app.job_sources.hired` (token + captcha gate, never bypass).
- Career pages: `app.job_sources.career_pages` (`data-ajas-job` cards).
- Watchdog: `app.job_sources.watchdog.retry_on_drift`.
- Canaries: `app.job_sources.canary` vs `*.html.sha256`.

## Normalization

- Benefits: `ajas.benefits.v1` in `app.job_sources.benefits`.
- Onsite/travel: `app.job_sources.work_arrangement`.
- Timezones: `app.job_sources.timezone`.
- Comp: `app.job_sources.comp` (equity / bonus / signing).
- Matching: batch autotune, embed cache, ANN recall harness, gap penalty,
  PRD stack boost, employment-type alignment, fair-norm, tie-breakers,
  counterfactual suggestions, mismatch counts.
- Resume: achievements vs responsibilities, employment-gap notes, language router.
- Taxonomy: community synonym import + deprecation aliases (`angularjs` → `javascript`).
- Apply: multi-step form machine (CAPTCHA → `needs_manual`), upload retrier,
  role-family cover templates, parameterized resume highlights.

## Email and follow-up

- OAuth refresh: `app.mail.oauth_hardening.refresh_access_token`.
- Interview times: `app.mail.interview_time` (IANA via location).
- Quoted/signature strip: `app.mail.strip_quotes`.
- Snooze: `app.mail.snooze` (weekday 09:00–17:00 UTC).

## Operator UI

- Match Why modal Copy, side-by-side compare, saved-search alerts,
  row quick actions, j/k/a/d/s/c/? triage keys, inbox grouping by job.

## Settings, ops, observability

- Per-site apply windows in Settings; resume version chooser on Apply.
- Email provider health + reconnect; Ops adapter last-success/drift mute.
- Algorithm flags: gap_penalty, stack_boost, fair_norm, ann_recall.
- Worker `X-Request-Id` propagation, structured error contexts, source
  latency histograms, adapter mute, PII scrub v2.

## Compliance, queues, API

- Consent log, GDPR resumes/logs, retention policy map, allowlist audit,
  tenant RBAC, secret rotation drift, queue backpressure, DLQ sample replay,
  envelope v2, `/health/matrix` probes.
- Pool autotune, list/detail cache, batch log/match writes, filter/sort indices,
  job revisions + diff API, match sort, email `q` filter, saved-search CRUD,
  ingest-scoped automation tokens, signed webhooks.
- CLI: `scripts/verify_adapters.py` (includes hired), `scripts/renormalize.py`,
  embeddings reindex orchestrator, legacy job migrate.

## Tests

- E2E ingest→match→apply unhappy paths and email threading/follow-up SLAs.

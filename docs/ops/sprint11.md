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
  counterfactual suggestions.

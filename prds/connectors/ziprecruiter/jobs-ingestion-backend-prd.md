# PRD: ZipRecruiter Jobs Ingestion — Backend

Status: Connector added
Feature: Job Source Integration (`feature-job-source-integration`)
Type: Backend
Flag: `ziprecruiter_adapter` (default on)
Live scrape: **not implemented**. `SOURCE_TYPES` stays `{greenhouse, lever}`.

## API availability
ZipRecruiter **does not** expose a public self-serve job-search API.

- Partner Jobs API (`api.ziprecruiter.com/partner/v0/job`): ATS-partner only; create/update/close jobs, not search.
- Legacy jobs/v1 (`api.ziprecruiter.com/jobs/v1`): required a publisher API key; not self-serve.
- Publisher XML: ZipRecruiter-push to approved aggregators, not a pull API.

AJAS therefore ingests **operator-supplied** jobs/v1 JSON, Partner job objects, publisher XML, and AJAS fixture pages. It does not call ziprecruiter.com.

## Field mapping (source of truth)
Executable table: `app.integrations.ziprecruiter_spec.FIELD_MAP`.

Accepts:
- AJAS fixture `{ jobs: [...] }` / `{ pages: [...] }` (cursor `next`)
- jobs/v1 `{ success, jobs, page, jobs_per_page, num_paginable_jobs }`
- Partner `{ job: { job_id, name, hiring_company, ... } }`
- Publisher XML (`<source><job>…`); `<email>` nodes are dropped

Nested `hiring_company.name` is flattened. Reject listings missing title, company, or postingUrl. Honor Retry-After on fixture envelopes.

## Pagination / rate limit
Cursor walk via `walk_pages`. Cap **20** requests / 60s. Retry-After is honored. Circuit after consecutive 5xx.

## HTTP
- `POST /api/v1/integrations/ingest/ziprecruiter` (JWT)
- `GET /api/v1/integrations/ziprecruiter/spec` (JWT)

## Out of scope
Live ZipRecruiter HTML scraping, adding `ziprecruiter` to `SOURCE_TYPES`, publisher OAuth.

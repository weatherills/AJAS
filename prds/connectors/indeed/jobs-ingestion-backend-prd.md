# PRD: Indeed Jobs Ingestion — Backend

Status: Connector added
Feature: Job Source Integration (`feature-job-source-integration`)
Type: Backend
Flag: `indeed_adapter` (default off)
Live scrape: **not implemented**. `SOURCE_TYPES` stays `{greenhouse, lever}`.

## API availability
Indeed **does not** expose a public job-search API.

- Publisher API (XML SERP feed): retired in 2023.
- Job Sync XML / Job Sync GraphQL: employer-outbound (ATS → Indeed). Requires Indeed partner credentials and cannot list third-party SERP jobs.
- Hosted publisher widget: iframe display only, no listing JSON.

AJAS therefore ingests **operator-supplied** Job Sync XML/JSON and AJAS fixture pages. It does not call indeed.com.

## Field mapping (source of truth)
Executable table: `app.integrations.indeed_spec.FIELD_MAP`.

Accepts:
- AJAS fixture `{ jobs: [...] }` / `{ pages: [...] }`
- Job Sync XML (`<source><job>…`)
- Job Sync JSON `{ sourcedJobPostings: [...] }`

Reject listings missing title, company, or postingUrl. Job Sync `<email>` nodes are dropped.

## Pagination / rate limit
Cursor walk via `walk_pages`. Cap 50 requests / 60s. Circuit after 5 consecutive 5xx.

## HTTP
- `POST /api/v1/integrations/ingest/indeed` (JWT)
- `GET /api/v1/integrations/indeed/spec` (JWT)

## Out of scope
Live Indeed HTML scraping, adding `indeed` to `SOURCE_TYPES`, Indeed Apply, partner OAuth.

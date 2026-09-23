# PRD: Glassdoor Jobs Ingestion — Backend

Status: Connector added
Feature: Job Source Integration (`feature-job-source-integration`)
Type: Backend
Flag: `glassdoor_adapter` (default on)
Live scrape: **not implemented**. `SOURCE_TYPES` stays `{greenhouse, lever}`.

## API availability
Glassdoor **does not** expose a public job-search API.

- Partner API (`api.glassdoor.com/api/api.htm`, `action=jobs`): closed to new applicants (2021–2023). Existing keys are not self-serve.
- Remaining Glassdoor APIs are employer-facing (post jobs, manage profiles), not listing search.
- HTML scraping hits aggressive bot defense (Sprint 13 cooldown) and is out of the Job Source PRD.

AJAS therefore ingests **operator-supplied** Partner-API envelopes and AJAS fixture pages. It does not call glassdoor.com.

## Field mapping (source of truth)
Executable table: `app.integrations.glassdoor_spec.FIELD_MAP`.

Accepts:
- AJAS fixture `{ jobs: [...] }` / `{ pages: [...] }`
- Historical Partner envelope `{ success, response: { jobs, currentPageNumber, totalNumberOfPages } }`

Nested `employer.name` and `location.name` are flattened. Reject listings missing title, company, or postingUrl. Private/expired rows are skipped.

## Pagination / rate limit
Cursor walk via `walk_pages`. Conservative cap **20** requests / 60s (Glassdoor block detection). HTTP 403 is fail-closed (permanent). Captcha is never bypassed.

## HTTP
- `POST /api/v1/integrations/ingest/glassdoor` (JWT)
- `GET /api/v1/integrations/glassdoor/spec` (JWT)

## Out of scope
Live Glassdoor HTML scraping, adding `glassdoor` to `SOURCE_TYPES`, reviews/salary APIs.

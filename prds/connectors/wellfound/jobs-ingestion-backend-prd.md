# PRD: Wellfound Jobs Ingestion — Backend

Status: Connector added
Feature: Job Source Integration (`feature-job-source-integration`)
Type: Backend
Flag: `wellfound_adapter` (default off)
Live scrape: **not implemented**. `SOURCE_TYPES` stays `{greenhouse, lever}`.

## API availability
Wellfound **does not** expose a public job-search API.

- AngelList REST (`api.angel.co`) is retired.
- Consumer GraphQL (`JobSearchResults` / `JobSearchResultsX`) is session, CSRF, and bot gated.
- Recruiter MCP OAuth is not a job-search API.

AJAS therefore ingests **operator-supplied** GraphQL job-search envelopes, startup listing payloads, and AJAS fixture pages. It does not fetch wellfound.com or api.angel.co.

## Auth
- Token required: `WELLFOUND_API_TOKEN` or `remember_token()`. Missing token → `needs_auth`.

## Field mapping (source of truth)
Executable table: `app.integrations.wellfound_spec.FIELD_MAP`.

Accepts:
- AJAS fixture `{ jobs: [...] }` / `{ pages: [...] }`
- GraphQL `{ data: { talent: { jobSearchResults | JobSearchResultsX } } }` (jobs array or edges/nodes)
- Startup `{ startup: { name, slug, jobListings|jobs } }`

Reject listings missing title, company, or postingUrl. Recruiter/candidate emails are dropped. Private/expired rows are skipped.

## Pagination / rate limit
Cursor walk via `walk_pages`. Cap **20** requests / 60s. Circuit after consecutive 5xx.

## HTTP
- `POST /api/v1/integrations/ingest/wellfound` (JWT)
- `GET /api/v1/integrations/wellfound/spec` (JWT)

## Out of scope
Live Wellfound HTML scraping, GraphQL session/CSRF bypass, adding `wellfound` to `SOURCE_TYPES`.

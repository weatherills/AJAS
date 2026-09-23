# PRD: Workday Jobs Ingestion — Backend

Status: Connector added
Feature: Job Source Integration (`feature-job-source-integration`)
Type: Backend
Flag: `workday_adapter` (default off)
Live scrape: **not implemented**. `SOURCE_TYPES` stays `{greenhouse, lever}`.

## API availability
Workday **does not** expose a public job-search API for aggregators.

- Official REST/SOAP (HCM / Recruiting): tenant-customer only. No self-serve credentials for reading third-party boards.
- Career-site CXS JSON (`POST /wday/cxs/{tenant}/{site}/jobs`, page size 20): undocumented, unauthenticated per tenant, fronted by Akamai. Not a documented public contract.
- HTML career pages: out of the Job Source PRD (fixture HTML parser already exists separately).

AJAS therefore ingests **operator-supplied** CXS list/detail envelopes and AJAS fixture pages. It does not call myworkdayjobs.com.

## Field mapping (source of truth)
Executable table: `app.integrations.workday_spec.FIELD_MAP`.

Accepts:
- AJAS fixture `{ jobs: [...] }` / `{ pages: [...] }`
- CXS list `{ total, jobPostings: [...] }` (company/host/site on the envelope)
- CXS detail `{ jobPostingInfo: { jobReqId, jobDescription, timeType, startDate } }`

Reject listings missing title, company, or postingUrl. Private/expired rows are skipped.

## Pagination / rate limit
Cursor walk via `walk_pages`. Cap **20** requests / 60s (CXS page size). Circuit after consecutive 5xx.

## HTTP
- `POST /api/v1/integrations/ingest/workday` (JWT)
- `GET /api/v1/integrations/workday/spec` (JWT)

## Out of scope
Live CXS fetch, adding `workday` to `SOURCE_TYPES`, Workday Apply, tenant OAuth.

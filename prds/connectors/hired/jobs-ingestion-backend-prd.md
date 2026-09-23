# PRD: Hired Jobs Ingestion — Backend

Status: Connector added
Feature: Job Source Integration (`feature-job-source-integration`)
Type: Backend
Flag: `hired_adapter` (default on)
Live scrape: **not implemented**. `SOURCE_TYPES` stays `{greenhouse, lever}`.

## API availability
Hired **does not** expose a public job-search API.

- Hired is a recruiter/candidate marketplace, not a job board.
- ATS partner integrations post roles *to* Hired (employer-outbound). They cannot list third-party marketplace roles for aggregators.
- Recruiter JSON historically used `positions` and candidate `matches` envelopes, gated by session tokens and CAPTCHA.

AJAS therefore ingests **operator-supplied** positions/matches envelopes and AJAS fixture pages. It does not call hired.com. CAPTCHA is never bypassed.

## Auth
- Token required: `HIRED_API_TOKEN` or `remember_token()`. Missing token → `needs_auth`.
- CAPTCHA in the fixture/HTML → `needs_manual`, empty jobs, `bypass: false`.

## Field mapping (source of truth)
Executable table: `app.integrations.hired_spec.FIELD_MAP`.

Accepts:
- AJAS fixture `{ jobs: [...] }` / `{ pages: [...] }`
- `{ positions: [...] }` (company/location may be nested objects)
- `{ matches: [{ position, candidate }] }` — candidate/email fields are dropped

Reject listings missing title, company, or postingUrl. Private/expired rows are skipped.

## Pagination / rate limit
Cursor walk via `walk_pages`. Cap **20** requests / 60s. Circuit after consecutive 5xx.

## HTTP
- `POST /api/v1/integrations/ingest/hired` (JWT)
- `GET /api/v1/integrations/hired/spec` (JWT)

## Out of scope
Live Hired HTML scraping, CAPTCHA solving, adding `hired` to `SOURCE_TYPES`, marketplace apply.

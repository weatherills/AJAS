# PRD: LinkedIn Jobs Ingestion — Backend

Status: Gap pass complete
Feature: Job Source Integration (`feature-job-source-integration`)
Type: Backend
Flag: `linkedin_adapter` (default off)
Live scrape: **not implemented**. Fixture JSON only. `SOURCE_TYPES` stays `{greenhouse, lever}`.

## Overview
Ingest LinkedIn job listings from operator-supplied fixture pages, normalize them onto the internal posting schema, paginate with cursors, dedupe, throttle, and emit PII-safe telemetry. Private and expired posts are skipped.

## Field mapping (source of truth)
Executable table: `app.integrations.linkedin_spec.FIELD_MAP`.

| LinkedIn field | Aliases | Internal | Type | Nullable | Fallback |
| --- | --- | --- | --- | --- | --- |
| id | jobId, source_posting_id, entityUrn, urn | sourcePostingId | string | no | canonical_id[:12] |
| title | jobTitle, name | title | string | no | — (reject) |
| company | companyName, employer, companyDetails | company | string | no | — (reject) |
| location | jobLocation, formattedLocation | location | string | yes | empty |
| description | body, content, jobDescription | description | string | yes | empty |
| apply_url | url, postingUrl, link | postingUrl | string | no | — (reject) |
| employment_type | type, jobType, workplaceTypes | employmentType | string | yes | empty |
| postedAt | posted_at, listedAt, datePosted | postedAt | datetime | yes | empty |
| easyApply | easy_apply, apply_method | applyMethod | enum | no | easy_apply on LinkedIn host |
| external_apply_url | externalApplyUrl | externalApplyUrl | string | yes | empty |
| status | visibility, jobState | visibility | enum | no | public |

Reject listings missing title, company, or postingUrl.

## Pagination
- Mode: **cursor** (offset is not used).
- Window size: 25 listings per page.
- Max pages: 20.
- Stop conditions: empty page, no next cursor, duplicate cursor, search limit reached, rate cap, max pages, circuit open.
- Fixture shape: `{ cursor, jobs, nextCursor }` or `{ pages: [ { cursor, jobs, nextCursor } ] }`.

## Deduping
Listing identity = `slug(title)|slug(company)|slug(location)|slug(postedAt)|na`.
Same listing key is a duplicate even when tracking URLs differ. Content-hash + postingUrl remains a secondary fingerprint.

## Rate limiting, retries, circuit
Plan: `RATE_PLAN["ingest"]`.

- Cap: 50 requests / 60s window, jitter 0.35s.
- Retry 429/408/503/504 with exponential backoff (base 0.25s, cap 8s, max 4 attempts).
- Circuit opens after 5 consecutive 5xx; stays open 300s.
- Counters: requests, retries, rate_limited, circuit_open, transient, permanent, captcha, timeout, private_skipped, expired_skipped, deduped.

## Edge cases
- **Private / unlisted / confidential**: skip, increment `privateSkipped`, audit `skipped_private`.
- **Expired / closed / filled**: skip, increment `expiredSkipped`, audit `skipped_expired`.
- **Robots / missing site-policy consent**: fail closed (`robots_or_consent`).
- **Flag off**: return no jobs (`flag_off`).
- **Circuit open**: return no jobs (`circuit_open`).

## Error states
| Class | Retry | Action |
| --- | --- | --- |
| ok | no | continue |
| rate_limited | yes | backoff |
| transient / timeout | yes | retry then abort |
| permanent | no | fail |
| captcha / challenge | no | needs_manual (never bypass) |

## Credentials / session
Sealed in-memory store (`linkedin_session.SealedSessionStore`):
- TTL 3600s, refresh when ≤300s remain, max 3 accounts.
- Tokens XOR+HMAC sealed; public APIs return `tokenHash` never plaintext.
- States: anonymous → active → expiring → expired / revoked. Rotation on refresh.

## Telemetry
Events (PII-safe): fetch, fetch_page, deduped, skipped_private, skipped_expired, retry, rate_limited, circuit_open.
Redact email, phone, tokens, cookies, resume bytes. See `linkedin_audit.sanitize`.

## Success metrics
- Fetch success ≥ 98%
- Dedupe catch rate ≥ 5% when duplicates are present
- Median runtime ≤ 8000ms
- QA: flags default off, SOURCE_TYPES unchanged, captcha never bypassed, receipts on attempts, private/expired skipped, audit redacted.

## HTTP
- `POST /api/v1/integrations/ingest/linkedin` — fixture ingest (JWT)
- `GET /api/v1/integrations/linkedin/spec` — executable contract bundle (JWT)
- `GET/POST /api/v1/integrations/linkedin/session` — sealed session (JWT)

## Out of scope
Live LinkedIn HTML scraping, adding `linkedin` to `SOURCE_TYPES`, Graph/Settings OAuth changes.

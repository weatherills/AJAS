# PRD: LinkedIn Easy Apply — Backend

Status: Gap pass complete
PRD ID (AJAS): 7b3b3357-bfb8-406f-b3ed-4f7fbc9e152e
Feature: Auto-Apply (`feature-auto-apply`)
Type: Backend
Flag: `linkedin_easy_apply` (default off; `linkedin_adapter` also permits submit in tests)

## Overview
Submit Easy Apply packages from a mapped profile, resume/cover attachments, and approved Q&A. Throttle, retry transients, fail closed on captcha/challenges, and always write a receipt plus a PII-safe audit event. Live browser automation that solves captchas is **out of scope**.

## Required / optional field matrix
Executable table: `EASY_APPLY_FIELDS` in `app.integrations.linkedin_spec`.

| Profile field | LinkedIn field | Required | Validation | User remediation |
| --- | --- | --- | --- | --- |
| full_name | name | yes | non-empty, max 100 | Add your full name in profile settings. |
| email | email | yes | RFC-like email | Use a valid email address. |
| phone | phone | no | 7+ digits if present | Add a reachable phone number. |
| location | location | no | max 120 | Set a city or remote location. |
| linkedin_url | linkedinProfile | no | must contain linkedin.com/in/ | Paste your public LinkedIn profile URL. |
| resume | resume | yes | PDF/DOCX ≤ 5 MB | Upload a PDF or DOCX resume under 5 MB. |
| cover_letter | coverLetter | no | PDF/DOCX/TXT/MD ≤ 5 MB or generated template | Attach a cover letter or leave blank. |

Autofill mapping: `DEFAULT_MAP["linkedin"]` / `PROFILE_TO_LINKEDIN`.

## Attachment handling
Policy (`ATTACHMENT_SPEC`):
- Resume required: `application/pdf` or DOCX, max 5 MB.
- Cover letter optional: PDF, DOCX, text/plain, text/markdown, max 5 MB.
- Cover template: `Dear {company} hiring team, … {title} … {location} … {name}`.
  Mode `cover_letter_mode=generate` renders the template when no cover file is attached.
- Q&A answers: optional, max 2000 chars, from approved templates.

## Error matrix
| Code | HTTP | Status | Retry | User prompt / action |
| --- | --- | --- | --- | --- |
| MISSING_REQUIRED | 400 | failed | no | Required Easy Apply fields are missing. / fix_profile |
| INVALID_EMAIL | 400 | failed | no | The email on your profile is not valid. / fix_profile |
| INVALID_PHONE | 400 | failed | no | The phone number needs at least seven digits. / fix_profile |
| INVALID_LINKEDIN_URL | 400 | failed | no | LinkedIn profile URL must contain linkedin.com/in/. / fix_profile |
| ATTACHMENT_TYPE | 400 | failed | no | Resume must be PDF or DOCX. / replace_file |
| ATTACHMENT_SIZE | 400 | failed | no | Each attachment must be 5 MB or smaller. / replace_file |
| MISSING_RESUME | 400 | failed | no | A resume file is required. / attach_resume |
| PRIVATE_JOB | 409 | failed | no | This posting is private. / skip |
| EXPIRED_JOB | 409 | failed | no | This posting has expired. / skip |
| RATE_LIMIT | 429 | rate_limited | yes | Rate limit reached; AJAS waits and retries. / backoff |
| SESSION_EXPIRED | 401 | needs_manual | no | Reconnect the LinkedIn account, then retry. / reconnect |
| CAPTCHA | 428 | needs_manual | no | Complete the CAPTCHA in LinkedIn, then retry from Review. Never bypass. abort |
| CHALLENGE | 428 | needs_manual | no | Finish the security challenge in the browser, then retry. Never bypass. abort |
| TIMEOUT | 504 | failed | yes | Timed out; retried with backoff then aborted. / retry_then_abort (max 4) |
| FLAG_OFF | 200 | disabled | no | Easy Apply is turned off. / enable_flag |

## Captcha / challenge / timeout fallback
- Detect recaptcha/hcaptcha/turnstile/cf-challenge → `needs_manual`, HITL, **bypass=false**.
- Detect checkpoint / unusual activity / verify it's you → same HITL abort.
- Timeout (408/504 or timeout copy) → retry with backoff, then abort with a receipt.
- User prompts always returned on those paths.

## Rate limiting
`RATE_PLAN["easy_apply"]`: 10 / 60s, jitter 0.2s, max 4 attempts, same circuit as ingest.

## Audit & receipts
Every attempt writes a receipt (`receiptId`, confirmation `EA-…` on success, fields sent, attachment names, answers).
Telemetry events are sanitized (no email/phone/token/resume). GET `/api/v1/integrations/linkedin/receipts`.

## Session
Optional `accountId`. Expired/revoked/anonymous sessions return `SESSION_EXPIRED` and do not submit.

## Success metrics
Easy Apply completion ≥ 80% of attempts in the sample. Median runtime ≤ 8s. Receipt on every attempt. Captcha never bypassed.

## HTTP
- `POST /api/v1/integrations/linkedin/easy-apply` (JWT)
- `POST /api/v1/integrations/linkedin/e2e` — ingest → match/review → Easy Apply
- `GET /api/v1/integrations/linkedin/spec`

## Out of scope
Solving captchas, live LinkedIn DOM automation, adding LinkedIn to Greenhouse/Lever `SOURCE_TYPES`.

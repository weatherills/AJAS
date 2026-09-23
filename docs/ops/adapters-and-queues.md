# Adapters and queues

Operating notes for ingestion, matching, apply, and email workers.

## Sources

- **Greenhouse / Lever** — production adapters. Public board HTTP, allowlisted
  hosts, per-tenant rate limits, and a process-wide cap (`120/min`, daily 10k).
- **Indeed / LinkedIn** — extra-board adapters (`FLAG_INDEED_ADAPTER` /
  `FLAG_LINKEDIN_ADAPTER`, default on). Indeed stays fixture ingest.
  LinkedIn guest search and voyager Easy Apply are opt-in live sockets
  (`LINKEDIN_LIVE`, same pattern as `IMAP_LIVE`). Captcha/checkpoint never
  bypasses. `SOURCE_TYPES` stays `{greenhouse, lever}`.
  `FLAG_SITE_POLICY_CONSENT` plus robots.txt must pass before any HTTP.
  When the flags are on, `POST /api/v1/integrations/ingest/{indeed|linkedin}`
  (LinkedIn also `POST /linkedin/search` and `POST /linkedin/easy-apply`)
  normalizes, dedupes, detects Easy Apply vs external, and records ingest
  metrics. Refresh: timer `integrations_refresh` (no-op while flags are off).
- **Greenhouse Harvest** — optional application-status reader
  (`FLAG_GREENHOUSE_HARVEST`). Public board crawl is unchanged.
- **Gmail / Drive / Slack** — optional (`FLAG_GMAIL_ADAPTER`, `FLAG_GOOGLE_DRIVE`,
  `FLAG_SLACK_NOTIFY`). Microsoft Graph remains the default mail transport.

Queues: `crawl-runs` → `job-fetch`. Poison after 10 dequeue attempts.

## Matching

Queues: `match-compute`. Sync compute stays in-process; rank fans out after 10
pairs. Feature vectors log as `ajas.match.ltr`. Reindex: `python scripts/reindex_embeddings.py`.

## Auto-Apply

Queues: `auto-apply-requests`, `auto-apply-submits`, `auto-apply-webhooks`.
Retries use exponential backoff (`retry_backoff_seconds`). Attachments: PDF/DOCX
resume and PDF/DOCX/TXT/MD cover letter, 5 MB. Idempotency on user + job +
resume. Bulk UI still opens Apply one selected job at a time.

## Email

Graph webhook `POST /api/webhooks/graph/mail` enqueues `mail-ingest`. IMAP/SMTP
health reports `transport: graph` and `imapConfigured: false`. Bounce webhook
stays on `MAIL_BOUNCE_WEBHOOK_SECRET`. Graph delta follows `@odata.nextLink`
until `@odata.deltaLink` (capped at 50 pages per poll).

## Flags and audit

- `GET /api/v1/ops/flags` — adapter/automation flags
- `GET /api/v1/ops/audit` — admin automated-action log
- `GET /api/health` — workers + dependency probes

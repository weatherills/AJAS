# Adapters and queues

Operating notes for ingestion, matching, apply, and email workers.

## Sources

- **Greenhouse / Lever** — production adapters. Public board HTTP, allowlisted
  hosts, per-tenant rate limits, and a process-wide cap (`120/min`, daily 10k).
- **Indeed / LinkedIn** — optional fixture adapters (`FLAG_INDEED_ADAPTER` /
  `FLAG_LINKEDIN_ADAPTER`). Live HTML scraping is out of the Job Source PRD and
  is not implemented. `FLAG_SITE_POLICY_CONSENT` plus robots.txt must pass
  before any HTTP.

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
stays on `MAIL_BOUNCE_WEBHOOK_SECRET`.

## Flags and audit

- `GET /api/v1/ops/flags` — adapter/automation flags
- `GET /api/v1/ops/audit` — admin automated-action log
- `GET /api/health` — workers + dependency probes

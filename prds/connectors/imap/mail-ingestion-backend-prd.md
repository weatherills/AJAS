# PRD: IMAP/SMTP Mail Connector — Backend

Status: Connector added
Feature: Email Ingestion & Reply (`feature-email-ingestion-reply`) extra transport
Type: Backend
Flag: `imap_transport` (default on)
Live fetch: **opt-in**. Microsoft Graph remains the Email PRD mailbox.

## API availability
IMAP/SMTP are standard mailbox protocols, not a public job API.

- RFC3501 IMAP FETCH / UID SEARCH
- RFC5322 messages
- SMTP send (RFC5321) over SSL/STARTTLS

AJAS therefore ingests **operator-supplied** RFC822 and FETCH envelopes by default. Live `imaplib`/`smtplib` sockets open only when all of these pass: `IMAP_LIVE`, `IMAP_USE_SSL`, credentials, and `IMAP_ALLOWED_HOSTS`.

## Auth
- Credentials: `IMAP_HOST`, `IMAP_USERNAME`, `IMAP_PASSWORD` (optional `SMTP_HOST`).
- Fixture sync does not require credentials.
- `live: true` without credentials → `needs_auth`.
- Live connect off the allowlist or without TLS → `live_disabled`.

## Field mapping (source of truth)
Executable table: `app.integrations.imap_spec.FIELD_MAP`.

Accepts:
- AJAS fixture `{ messages: [...] }` / `{ pages: [...] }`
- RFC822 bytes/text
- FETCH envelope `{ uid, envelope, body }` / `{ rfc822 }`

Folders map through `app.mail.imap_labels`. Recruiter intent uses `classify_email`.

## Pagination / rate limit
UID cursor (`sinceUid`). Cap **20** messages / 60s.

## HTTP
- `POST /api/v1/integrations/imap/sync` (JWT)
- `POST /api/v1/integrations/imap/send` (JWT)
- `GET /api/v1/integrations/imap/spec` (JWT)

## Out of scope
Replacing Graph as the Email PRD transport, shared mailboxes, calendar, unauthenticated host-from-request (SSRF).

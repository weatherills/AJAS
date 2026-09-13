# Sprint 12 operations

Sprint 12 adds tenancy, billing, sharing, localization, and operator product
surfaces on top of Sprint 11. Optional adapters and live HTML scraping stay
**off**. Stripe, Google SSO, IMAP/SMTP, and recruiter portal are in-process
scaffolds with flags/plans gating them.

Batch gates: [sprint12-batches.md](./sprint12-batches.md).

## Tenancy and billing

- Org/workspace model: `app.sprint12.tenants` (Owner / Admin / Member / Read-only).
- Invite emails land in an in-memory outbox (`template=tenant.invite`).
- Plans: Free / Pro / Team. Share links need Pro+. Recruiter portal and SSO need Team.
- Stripe checkout + `invoice.paid` webhook sync invoice status. No live Stripe calls.
- Soft cap at 80% of the plan meter, hard cap at 100%.

## Sharing and ranking

- Expiring share tokens for job/match views.
- Thumbs up/down adjust keyword/semantic weights.
- Feature store + offline harness, AB explanation styles, skill co-occurrence.

## Email, ingest, safety

- OAuth IMAP/SMTP connection records (not a live mailer).
- Classification labels: offer / interview / nurture / reject / followup.
- Sitemap crawler parses XML fixtures only.
- HTML sanitizer, context-aware PII, scam/JD warnings, tenant blocklists.

## UI

- Dark/light/system theme toggle.
- `en` / `fr` / `es` catalogs plus date/number formatting.
- Cookie banner, Help, Changelog, Legal, Admin, recruiter Share routes.
- Phone layout turns tables into cards.

## HTTP

| Route | Purpose |
| --- | --- |
| `GET/POST /api/v1/tenants` | Create/list workspaces |
| `POST /api/v1/tenants/{id}/invites` | Admin invite |
| `GET /api/v1/billing/usage` | Meters + invoices |
| `POST /api/v1/billing/stripe/webhook` | Invoice sync |
| `POST /api/v1/share/links` | Mint expiring token |
| `GET /api/v1/share/{token}` | Recruiter-limited view |
| `GET /api/v1/admin/overview` | Golden signals |
| `POST /api/v1/feedback/matches/{jobId}` | Thumbs vote |
| `GET /api/v1/legal` | Terms/privacy versions |
| `GET /api/v1/changelog` | Release highlights |
| `GET/POST /api/v1/api-keys` | Public API keys |
| `GET /api/v1/help` | Knowledge base |

Health `version` is `sprint12`. Responses include CSP + `X-RateLimit-*`.

## CLI

```
python scripts/ajas.py ingest
python scripts/ajas.py reindex
python scripts/ajas.py backfill
python scripts/ajas.py seed
python scripts/ajas.py adapters
bash scripts/bootstrap.sh
```

## Rollback

See [rollback.md](./rollback.md). Unset new plan features by assigning `free`.
Dark-mode and locale are client-only (`ajas.theme`, `ajas.locale`).

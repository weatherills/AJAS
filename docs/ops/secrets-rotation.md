# Secrets rotation playbook

Rotate AJAS secrets without downtime. Treat every value in Azure App Settings / Key Vault as
replaceable.

## Inventory

| Secret | Where it is read | Blast radius |
| --- | --- | --- |
| `COSMOS_CONNECTION_STRING` | `app.config.Settings` | All document reads/writes |
| `BLOB_CONNECTION_STRING` / `QUEUE_CONNECTION_STRING` | config | Resume blobs, mail attachments, queues |
| `AZURE_OPENAI_API_KEY` | matching + cover letters | Scoring and AI copy |
| `MICROSOFT_CLIENT_SECRET` | Settings OAuth | Graph ingest/reply |
| `SETTINGS_TOKEN_KEY` | Settings token seal | Encrypted Graph refresh tokens |
| `AUTO_APPLY_WEBHOOK_SECRET` | Auto-Apply webhooks | Vendor callbacks |
| `GREENHOUSE_SUBMIT_API_KEY` / `LEVER_SUBMIT_API_KEY` | Auto-Apply submitters | Live applications |
| `AUTH_JWT_SECRET` | JWT auth mode | Session verification |

## Rotation steps (staging first)

1. Create the new secret in Key Vault (or a second App Setting `*_NEXT`).
2. Dual-read in code already prefers the live env var; point the slot at the new value.
3. Restart Function App instances rolling (Azure does this per revision).
4. For Graph: disconnect/reconnect Microsoft 365 in Settings so refresh tokens are sealed with the new `SETTINGS_TOKEN_KEY`.
5. For Cosmos/Storage: swap connection strings only after the new account is replicated.
6. Revoke the old secret. Confirm `/api/health` and a Review list still succeed.
7. Record the rotation in the Settings audit trail (threshold no-op or a dedicated note).

## Automation hooks

- GitHub Actions cannot rotate production secrets; use Azure Key Vault rotation policies.
- After rotation, `GET /api/v1/ops/slo` and Settings GET should stay 200.
- Staging drill: clone this repo, set dummy values, restart `func start`, hit health.

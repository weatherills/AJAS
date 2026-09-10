# Production runbook

Local/dev stays on `AUTH_MODE=dev` with `Authorization: Bearer local-user` (or `local-admin` for Ops traces). Production uses the env flags below; none of them are required to start the Functions host.

## Auth

| Mode | How callers authenticate |
| --- | --- |
| `AUTH_MODE=dev` (default) | Bearer user id, optional `X-Role: admin`, or an issued `ajas.at.` session |
| `AUTH_MODE=aad` | Azure AD JWT (`AUTH_JWT_SECRET` HS256 **or** `AUTH_JWT_JWKS_URL` RS256). SPA reads `GET /api/v1/auth/config` and stores the access token in `sessionStorage` (`ajas_aad_token`) |

Session cookies: `POST /api/v1/auth/session` sets HttpOnly `ajas_sess`. Cookie-authenticated writes need `X-CSRF-Token` matching `csrfToken` from the session JSON (or the `X-CSRF-Token` response header). Bearer tokens skip CSRF so existing tests and scripts keep working.

## Secrets

Prefer app settings in Container Apps / Function App. Optional Key Vault hydration: set `KEY_VAULT_URI` (or `AZURE_KEY_VAULT_URI`). On boot, `hydrate_from_key_vault()` copies missing env vars from secrets named with lowercase hyphens (`azure-openai-api-key`, `microsoft-client-secret`, …). Local/dev leaves `KEY_VAULT_URI` unset.

Graph OAuth still needs `MICROSOFT_CLIENT_ID` + `MICROSOFT_CLIENT_SECRET`. Settings keeps the unconfigured Microsoft 365 banner when those are missing.

## CORS

`CORS_ALLOWED_ORIGINS` is a comma-separated allowlist. In `AUTH_MODE=dev`, `http://localhost:3000` and `http://127.0.0.1:3000` are always appended. Preflight: `OPTIONS` on `/api/health`, `/api/ready`, and a catch-all OPTIONS route.

## Probes

- Liveness: `GET /api/health` → `{ status, storage, authMode, features }`
- Readiness: `GET /api/ready` → same payload plus `ready: true`

Wire both into Container Apps / load balancer. `storage` is `cosmos` when `COSMOS_CONNECTION_STRING` is set, otherwise `memory`.

## Email bounce webhook

`POST /api/v1/email/webhooks/bounce` requires `X-Webhook-Secret` equal to `MAIL_BOUNCE_WEBHOOK_SECRET` (default `dev-bounce-secret`). Unsigned requests return 401.

## Ingestion alerts

When Ops `failureCount >= 3`, AJAS logs `ajas.ingestion.alert` and POSTs to `INGESTION_ALERT_WEBHOOK` if set. Demo-seed skip events do not page.

## Observability

In-process traces: `GET /api/v1/ops/traces` (admin). SLO samples: `GET /api/v1/ops/slo`. Set `APPLICATIONINSIGHTS_CONNECTION_STRING` or `OTEL_EXPORTER_OTLP_ENDPOINT` to emit `ajas.monitor` JSON for an exporter.

## Deploy

`.github/workflows/deploy-aca.yml` is a `workflow_dispatch` template for Azure Container Apps. It does not run on pull requests.

Smoke: `python scripts/smoke.py` with `AJAS_BASE_URL`. Restore drill: `python scripts/backup_drill.py` (hits health/ready and appends `docs/ops/restore-drills.log`).

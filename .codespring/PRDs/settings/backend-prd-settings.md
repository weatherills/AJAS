# Backend PRD: Settings
**Feature:** Settings  
**Type:** backend

Feature overview
Settings enables users to control three backend behaviors: 1) their AI match threshold for job recommendations, 2) connecting their Microsoft 365 email via OAuth to power email-based features, and 3) toggling ingestion from external job sources (Greenhouse, Lever). These settings persist per user in Cosmos DB and drive downstream services (matching, ingestion).

Scope & behavior
- Data model (Cosmos DB, partitioned by userId):
  - id: string (userId), partitionKey = userId
  - matchThreshold: number (0.10–0.99; default 0.70; precision 2 decimals)
  - emailConnection:
    - status: enum [disconnected, pending, connected, error]
    - provider: "microsoft" | null
    - tenantId: string | null
    - accountId: string | null (Graph user id or UPN)
    - scopes: string[] (granted Graph scopes)
    - lastVerifiedAt: ISO datetime | null
    - errorCode: string | null
    - secure: { refreshTokenEnc: string | null, expiresAt: ISO datetime | null } (never returned via API)
  - sources:
    - greenhouseEnabled: boolean (default false)
    - leverEnabled: boolean (default false)
  - audit: { createdAt, updatedAt, updatedBy }

- API (all endpoints require authenticated user; scope: self only)
  - GET /v1/settings
    - 200: returns { matchThreshold, emailConnection: {status, provider, tenantId, accountId, scopes, lastVerifiedAt}, sources, audit }
    - Redact secure fields.
  - PATCH /v1/settings
    - Body: any subset of { matchThreshold, sources: {greenhouseEnabled?, leverEnabled?} }
    - Validations: threshold within [0.10, 0.99], step 0.01; sources booleans only.
    - Effects:
      - On matchThreshold change: enqueue re-evaluation job (Azure Storage Queue: match-recalc) with { userId, oldThreshold, newThreshold, requestedAt }.
      - On source toggle true→false: stop future fetches; do not delete prior data. False→true: enqueue discovery job per enabled source (Queue: source-discovery) with { userId, source }.
    - 200 with updated settings. 400 on validation error. Idempotent.
  - POST /v1/settings/email/connect
    - Initiates Microsoft OAuth (Authorization Code + PKCE).
    - Body: { redirectUri }
    - Server returns { authUrl, state } and sets emailConnection.status = "pending".
    - Required scopes: ["offline_access","Mail.Read"] (extendable).
  - POST /v1/settings/email/callback
    - Body: { code, state, redirectUri }
    - Exchanges code via Microsoft Graph token endpoint.
    - On success: store refreshTokenEnc (encrypted at rest), expiresAt, provider="microsoft", tenantId, accountId, scopes; set status="connected", lastVerifiedAt=now.
    - On failure: set status="error", errorCode; 502 on upstream errors; 400 on invalid state/code.
  - POST /v1/settings/email/disconnect
    - Revokes local connection by deleting secure.refreshTokenEnc and setting status="disconnected"; does not call Graph revoke.
    - 200 success; idempotent.

- Security & privacy
  - Authentication via platform JWT; only owner may read/write their settings.
  - Refresh tokens stored encrypted at rest; never returned via API logs or responses.
  - Rate limits: 10 write ops/min/user; 3 email connect attempts/min/user.
  - Input validation and state parameter verification to prevent CSRF; PKCE required.

- Operational
  - P99 latency: <500ms for GET/PATCH; <1200ms for OAuth callback (token exchange).
  - Resiliency: queue operations must retry with exponential backoff; at-least-once delivery acceptable (idempotent consumers).
  - Observability: audit updates on every change; structured logs for OAuth errors (no secrets).

User-facing flows
- Threshold Slider
  - User adjusts slider -> client PATCH with new matchThreshold.
  - Backend validates, persists, enqueues match-recalc.
  - Edge cases: same value -> no-op; out-of-range -> 400.

- Connect Email (Microsoft 365)
  - Client calls email/connect -> receives authUrl -> user authorizes in Microsoft consent screen.
  - Graph redirects to callback -> backend exchanges code -> status->connected and persists tokens.
  - Edge cases: user denies consent -> status=error, 400 to client; expired code -> 400; repeated connect when connected -> 200 no-op.

- Source Toggles (Greenhouse/Lever)
  - Client PATCH sources flags.
  - true->false: ingestion workers skip this source for user.
  - false->true: enqueue discovery immediately.
  - Edge cases: unknown source key -> 400; no changes -> 200 unchanged.

Acceptance criteria
- GET returns settings without secure fields; 401 when unauthenticated; 403 when accessing another user.
- PATCH validates threshold to two decimals and range; persists and returns updated doc; creates exactly one queue message per change type.
- Toggling sources produces corresponding discovery/stop effects and is idempotent.
- email/connect returns a valid Microsoft OAuth URL with state and PKCE parameters; sets status=pending.
- email/callback exchanges code, persists encrypted refresh token, sets status=connected; handles Graph errors with 502 and sets status=error.
- email/disconnect clears secure fields and sets status=disconnected; subsequent GET reflects status.
- All writes update audit.updatedAt and updatedBy.
- PII/secrets never appear in logs or API responses.

Out of scope
- Frontend UI controls and rendering.
- Downstream matcher implementation and re-ranking logic.
- Actual ingestion workers for Greenhouse/Lever and email processing.
- Revoking tokens at Microsoft or multi-account linking.
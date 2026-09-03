# Settings — Product Requirements

> **Runbook phase:** Phase 3 &nbsp;·&nbsp; **Feature key:** `settings`
>
> Consolidated PRD for the "Settings" feature — combines the backend,
> database, and frontend requirements in one place. The canonical,
> CodeSpring-generated sources remain the source of truth:
> - [Backend PRD](../../.codespring/PRDs/settings/backend-prd-settings.md)
> - [Database PRD](../../.codespring/PRDs/settings/database-prd-settings.md)
> - [Frontend PRD](../../.codespring/PRDs/settings/frontend-prd-settings.md)

---

## Backend

### Backend PRD: Settings
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
---

## Database

### Database PRD: Settings
**Feature:** Settings  
**Type:** database

##### Feature: Settings (Match Threshold, Email Connection, Source Toggles)

- Scope: Persist per-user configuration for AI match threshold, Microsoft 365 OAuth connection state, and enabling/disabling job source integrations (Greenhouse, Lever).
- Tenancy: All records are scoped to a single user (user_id). One row in user_settings per user. Email connections are per user with at most one active Microsoft 365 connection.
- Security: OAuth tokens must be stored encrypted; never logged in cleartext. Audit all settings changes.

##### Entities & Relationships
- user_settings (1:1 with user): Stores the numeric threshold and source toggles. Optimistic concurrency via version.
- email_connections (N:1 to user): Stores Microsoft 365 OAuth credentials and sync/webhook cursors. Only one active per (user, provider).
- settings_audit_log (N:1 to user and to a changed entity): Immutable append-only log of changes for both user_settings and email_connections.

##### Constraints & Validation
- match_threshold: INT in [0, 100]. If NULL, system defaults to 70 (business default; not stored as a separate row).
- greenhouse_enabled, lever_enabled: BOOLEAN. If both false, system should still allow saving; downstream services must no-op sourcing.
- email_connections.provider: enum logical value 'microsoft_365'. Future providers can be added without schema change (free-form TEXT + validation at application).
- email_connections.status: one of ['pending', 'active', 'revoked', 'expired', 'error'].
- Only one active connection per (user_id, provider). Enforce via unique partial index or application-level guard.
- OAuth token fields (access_token_enc, refresh_token_enc) required when status = 'active' or 'pending'; must be NULL when 'revoked'.
- subscription_expires_at must be >= now when webhook_subscription_id is present.
- Audit entries required for any mutation to user_settings or email_connections with a non-empty field_mask.

##### Indexing
- user_settings: unique index on (user_id); index on (updated_at desc) for admin queries.
- email_connections: composite index (user_id, provider); partial unique index on (user_id, provider) where status = 'active'; index on (account_email) for lookup; index on (subscription_expires_at) to renew webhooks.
- settings_audit_log: index on (user_id, created_at desc), and (entity_id, created_at desc) for entity histories.

##### Data Lifecycle & Auditing
- Soft lifecycle via status in email_connections; do not hard-delete to preserve auditability.
- Rotate/refresh tokens before expires_at; write last_sync_status/last_sync_error on sync attempts.
- All changes to threshold, source toggles, and email connection status/credentials produce an audit row linking actor_id and field_mask.

##### Edge Cases & Behaviors
- If token is expired (now > expires_at), set status = 'expired' and queue a refresh; do not delete tokens.
- Revocation clears tokens (set to NULL), sets status = 'revoked', and records revoked_at.
- Threshold updates use version for optimistic locking: reject if version mismatches.
- Deleting a user should cascade-delete user_settings and email_connections or be blocked until archival, but audit log remains immutable (retain for compliance).
---

## Frontend

### Frontend PRD: Settings
**Feature:** Settings  
**Type:** frontend

Feature overview
Settings enables users to control how AJAS matches jobs and connects to their email/ATS sources. It includes: a match threshold slider to tune sensitivity, Microsoft 365 OAuth connection for email ingestion, and toggles to enable/disable ATS sources (Greenhouse, Lever). All settings are per-user and persist across sessions.

Scope & behavior
- General
  - Page sections: Matching Threshold, Email Connection, Sources.
  - Persist per authenticated user. Changes autosave and show inline status.
  - Optimistic UI when safe; otherwise show pending state until confirmation.
  - Accessibility: all controls keyboard operable; visible focus; labels; ARIA for slider and status messages.

- Matching Threshold (Slider)
  - Range: 0–100 (percent). Default: 70.
  - Step: 1. Display current value as “70%”.
  - Live preview text: “Fewer matches” near 100, “More matches” near 0.
  - Debounce save: 600 ms after last change; show “Saving…” then “Saved”.
  - Validation: clamp out-of-range inputs to bounds; non-numeric input ignored.
  - Error: show inline error “Couldn’t save threshold. Try again.” with Retry and Revert to last saved value.
  - Persistence: immediately reflected in UI after save; used by AI Matching Service downstream (no client logic change here).

- Email Connection (Microsoft 365 via OAuth to Microsoft Graph)
  - States:
    - Disconnected: CTA “Connect Microsoft 365”.
    - Connecting: spinner and “Continue in Microsoft window…”.
    - Connected: show account email, status badge “Connected”, last sync time (if provided by API), and actions: “Disconnect”, “Reconnect”.
    - Expired/Revoked: show warning badge “Action required” with “Reconnect”.
    - Error: display specific error (permission denied, popup blocked, network).
  - Flow triggers pop-up/redirect OAuth; handle popup blockers with fallback instructions and “Open Window” retry.
  - Scopes requested: offline_access, Mail.Read. Display summary “Read-only access to your mailbox”.
  - Disconnect confirmation modal: explain it stops future email ingestion; action revokes app tokens server-side. Keep past ingested data (not deleted).
  - Edge cases: user cancels consent; multiple accounts (show the connected account email); token refresh failure => prompt reconnect.

- Sources (Greenhouse, Lever toggles)
  - Each source row: name, description, toggle (On/Off), status text.
  - Default: Off.
  - Toggle saves immediately; show “Saving…/Saved/Error”.
  - Disabled state: if backend reports source unavailable/not configured for the user, show disabled toggle with tooltip “Not configured”.
  - Error: revert visual toggle to last saved state and show inline error with Retry.
  - No credential entry here; only enable/disable ingestion/use of that source.

User-facing flows
- Adjust Threshold
  1) User drags slider; value updates in label. 2) After 600 ms idle, save fires. 3) Show “Saving…”, then “Saved”. 4) On error: show inline error with Retry/Revert.

- Connect Email
  1) Click “Connect Microsoft 365”. 2) OAuth window opens; user consents. 3) On success, UI updates to Connected with account email and last sync. 4) On cancel/deny: return to Disconnected with error banner and Retry.

- Reconnect/Expired
  1) Click “Reconnect”. 2) Repeat OAuth flow. 3) On success, status returns to Connected.

- Disconnect Email
  1) Click “Disconnect” → confirm modal. 2) On confirm, set to Disconnected; show toast “Disconnected”.

- Toggle Source
  1) Switch On/Off. 2) Show “Saving…”. 3) On success, persist state; on failure, revert toggle and show error.

Acceptance criteria
- Slider renders 0–100 with step 1, default 70; keyboard arrows adjust by 1, PageUp/PageDown by 10.
- Slider change saves after 600 ms idle; no more than 1 in-flight save; latest value wins.
- Out-of-range values are clamped; on failed save, prior saved value is restored when user taps Revert.
- Email Connect button initiates OAuth; on success, connected account email is displayed and persisted.
- If popup is blocked, user sees guidance and a retry action opens the popup.
- Connected state shows “Reconnect” and “Disconnect”; “Disconnect” requires confirmation and results in Disconnected state.
- If token is expired/revoked, UI shows warning and offers Reconnect; after successful reconnect, status clears.
- Each source toggle persists immediately; on backend error, UI reverts and shows inline error message.
- Disabled source shows tooltip explaining unavailability and cannot be toggled.
- All state changes display non-intrusive inline status and/or toast messages and are screen-reader announced.

Out of scope
- Non-Microsoft email providers (e.g., Gmail).
- Managing OAuth scopes beyond display, manual token management UI.
- Configuring Greenhouse/Lever credentials or account linking workflows.
- Deleting previously ingested data.
- Admin/global settings; multi-tenant org controls.
- Notification preferences or other unrelated settings.
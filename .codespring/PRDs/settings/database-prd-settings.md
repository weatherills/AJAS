# Database PRD: Settings
**Feature:** Settings  
**Type:** database

## Scope
Persist user-specific Settings for AJAS:
- Match threshold for AI Matching Service
- Microsoft 365 email connection (OAuth via Microsoft Graph)
- Source toggles for Greenhouse and Lever

## Entities & Relationships
- user_settings: 1:1 per user. Stores threshold and source toggles. Partitioned by user_id.
- email_connections: N:1 per user. Stores Microsoft 365 OAuth connection(s) and sync/webhook metadata. Partitioned by user_id. For MVP, provider must equal "microsoft_365".

## Constraints & Validation
- match_threshold INT in [0, 100]; null means use system default (70) at read-time.
- greenhouse_enabled, lever_enabled default false.
- email_connections.connection_status ENUM (TEXT): ["connected", "pending_consent", "revoked", "error"].
- Unique constraints (logical):
  - user_settings.user_id unique (single settings row per user).
  - email_connections unique per (user_id, provider, account_email) active connection.
- Tokens:
  - Store only encrypted refresh token (refresh_token_ciphertext). Access tokens should be ephemeral; if persisted, only expiry metadata is stored.
  - refresh_token_expires_at required when refresh_token_ciphertext is present.
- Webhook subscription (optional): if webhook_subscription_id is set, webhook_expiration must be set.

## Behavioral Notes
- Threshold Slider:
  - Writes update user_settings.match_threshold, updated_at. Reject updates outside [0, 100].
  - Reads: if null, return default 70.
- Connect Email (Microsoft 365):
  - On initial OAuth success, create email_connections row with status "connected", set consented_scopes, token_obtained_at, refresh_token_ciphertext, refresh_token_expires_at, account_email, graph_tenant_id, account_id.
  - On token refresh failure, set connection_status="error" and last_error_code/message.
  - On user disconnect, set connection_status="revoked", revoked_at; do not delete row.
  - Webhook renewal updates webhook_subscription_id and webhook_expiration; failures capture last_error_*.
- Source Toggles:
  - Enable/disable ingestion per source by flags in user_settings. Ingestion services must read these flags before processing.
  - Disabling a source has no side effects on historical data; it only prevents new fetches.

## Edge Cases
- Multiple email accounts: allowed; ensure uniqueness per (user_id, provider, account_email). Only rows with connection_status="connected" are considered active.
- Expired tokens: if current time > refresh_token_expires_at, treat as "error" until re-auth.
- Webhook expiration passed: continue polling fallback if applicable, but mark last_error_* if renewal fails.

## Partitioning & Indexing (Cosmos DB oriented)
- Partition key: pk = user_id for both tables (high cardinality, co-locates user data, minimizes cross-partition queries).
- Recommended logical indexes/queries:
  - user_settings by user_id (point read)
  - email_connections by user_id and filter on connection_status="connected" and provider="microsoft_365".

## Security & PII
- Store refresh_token_ciphertext only (application-layer encryption/KMS). Never store plaintext tokens.
- account_email and account_id are PII; restrict access via RBAC and minimize query projections.

## Audit & Timestamps
- created_at, updated_at on all rows (UTC TIMESTAMPTZ). Update updated_at on any write.
- last_sync_at updated by ingestion workers only; user writes must not modify it.

## Acceptance (DB-Level)
- Exactly one user_settings row per user can exist.
- Writes outside threshold range rejected.
- Revoked connections remain queryable but excluded from "active" results.
- Toggling sources updates only user_settings and is immediately observable by ingestion services.
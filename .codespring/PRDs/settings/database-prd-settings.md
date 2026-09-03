# Database PRD: Settings
**Feature:** Settings  
**Type:** database

### Feature: Settings (Match Threshold, Email Connection, Source Toggles)

- Scope: Persist per-user configuration for AI match threshold, Microsoft 365 OAuth connection state, and enabling/disabling job source integrations (Greenhouse, Lever).
- Tenancy: All records are scoped to a single user (user_id). One row in user_settings per user. Email connections are per user with at most one active Microsoft 365 connection.
- Security: OAuth tokens must be stored encrypted; never logged in cleartext. Audit all settings changes.

### Entities & Relationships
- user_settings (1:1 with user): Stores the numeric threshold and source toggles. Optimistic concurrency via version.
- email_connections (N:1 to user): Stores Microsoft 365 OAuth credentials and sync/webhook cursors. Only one active per (user, provider).
- settings_audit_log (N:1 to user and to a changed entity): Immutable append-only log of changes for both user_settings and email_connections.

### Constraints & Validation
- match_threshold: INT in [0, 100]. If NULL, system defaults to 70 (business default; not stored as a separate row).
- greenhouse_enabled, lever_enabled: BOOLEAN. If both false, system should still allow saving; downstream services must no-op sourcing.
- email_connections.provider: enum logical value 'microsoft_365'. Future providers can be added without schema change (free-form TEXT + validation at application).
- email_connections.status: one of ['pending', 'active', 'revoked', 'expired', 'error'].
- Only one active connection per (user_id, provider). Enforce via unique partial index or application-level guard.
- OAuth token fields (access_token_enc, refresh_token_enc) required when status = 'active' or 'pending'; must be NULL when 'revoked'.
- subscription_expires_at must be >= now when webhook_subscription_id is present.
- Audit entries required for any mutation to user_settings or email_connections with a non-empty field_mask.

### Indexing
- user_settings: unique index on (user_id); index on (updated_at desc) for admin queries.
- email_connections: composite index (user_id, provider); partial unique index on (user_id, provider) where status = 'active'; index on (account_email) for lookup; index on (subscription_expires_at) to renew webhooks.
- settings_audit_log: index on (user_id, created_at desc), and (entity_id, created_at desc) for entity histories.

### Data Lifecycle & Auditing
- Soft lifecycle via status in email_connections; do not hard-delete to preserve auditability.
- Rotate/refresh tokens before expires_at; write last_sync_status/last_sync_error on sync attempts.
- All changes to threshold, source toggles, and email connection status/credentials produce an audit row linking actor_id and field_mask.

### Edge Cases & Behaviors
- If token is expired (now > expires_at), set status = 'expired' and queue a refresh; do not delete tokens.
- Revocation clears tokens (set to NULL), sets status = 'revoked', and records revoked_at.
- Threshold updates use version for optimistic locking: reject if version mismatches.
- Deleting a user should cascade-delete user_settings and email_connections or be blocked until archival, but audit log remains immutable (retain for compliance).
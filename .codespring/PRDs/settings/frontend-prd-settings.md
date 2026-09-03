# Frontend PRD: Settings
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
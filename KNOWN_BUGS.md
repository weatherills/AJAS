# Known bugs

Recorded 2026-09-11 after the Graph / Auto-Apply / Review must-fixes. These are remaining defects, not a feature wishlist. PRD items marked out of scope are listed at the bottom so they are not re-filed as bugs.

## Open

### Graph uses the first mailbox token in the process

`HttpGraphClient` is constructed once with `_settings_access_token()`, which walks every Settings user and returns the first token that refreshes. Poll, reply, and subscription renew then call Graph as that mailbox, not as the account being processed.

**Where:** `backend/app/mail/graph.py` (`_settings_access_token`, `default_graph_client`)

**Impact:** A second connected Microsoft account can ingest or send as the wrong user.

### Disconnect does not cancel the Graph webhook

Settings disconnect revokes the local connection and clears tokens. It does not DELETE the Graph subscription, so Microsoft can keep POSTing to `/api/webhooks/graph/mail` until the subscription expires (~42 hours).

**Where:** `backend/app/settings/service.py` (`disconnect`); no Graph unsubscribe in `backend/app/mail/`

**Impact:** Stale notifications after the user disconnects Outlook. Client-state checks still reject foreign payloads, but the endpoint keeps receiving traffic.

### Disconnect does not revoke the Microsoft refresh token

Local tokens are deleted. AJAS does not call Microsoft’s token revocation endpoint, so the issued refresh token stays valid at Entra ID until it expires. The Settings PRD documents this.

**Where:** `backend/app/settings/service.py` (`disconnect`)

**Impact:** A copied refresh token still works against Graph after “Disconnect” in AJAS.

### Cosmos stores load every document into memory

Mail, Auto-Apply, Matching, Learning, Review, and Job Sources Cosmos adapters run `SELECT * FROM c` (cross-partition) and hydrate an in-memory store on each mutating call.

**Where:** `backend/app/*/cosmos_store.py` (`_hydrate`)

**Impact:** Latency and cost grow with data size; a Functions instance can mix tenants in that in-memory snapshot.

### Cover letter “Upload” cannot read PDF or Word files

The Apply modal accepts `.pdf`, `.doc`, and `.docx`, then `FileReader.readAsText`. Binary files fail or paste garbage. `.txt` / `.md` and the paste box work.

**Where:** `frontend/src/components/ApplyModal.tsx`

**Impact:** Users who pick a PDF cover letter see an error and must paste text.

### Greenhouse / Lever live submit is off unless flagged

`AUTO_APPLY_LIVE_SUBMIT` defaults to false. Without the flag and vendor API keys, API-path attempts record a simulated submit. Turning the flag on in production has not been verified against real Greenhouse/Lever.

**Where:** `backend/app/config.py` (`auto_apply_live_submit`); `backend/app/auto_apply/service.py`

**Impact:** Default deploys do not actually post applications to vendor APIs.

### Semantic matching is a hash vector without Azure OpenAI

If `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` are unset, matching uses `HashEmbedder` (64-dim token hashes) instead of embeddings.

**Where:** `backend/app/matching/embedder.py` (`default_embedder`)

**Impact:** Rankings are keyword-hash similarity, not the hybrid semantic score the Matching PRD describes.

### Attachment malware scan is EICAR-only

Inbound mail is checked for the EICAR test signature. There is no production antivirus. The Email PRD lists full scanning as out of scope.

**Where:** `backend/app/mail/scan.py`

**Impact:** Real malware in recruiter attachments is stored if it is under the size cap.

### Frontend talks to the live API unless mock is forced

`VITE_USE_MOCK === 'true'` is required for the in-browser demo. A plain `npm run dev` calls `/api` on the Functions host (proxied to `:7071`).

**Where:** `frontend/src/api/index.ts`

**Impact:** Local UI looks empty or errors if the backend is not running.

## Out of scope (not tracked as bugs)

- Gmail / IMAP, shared mailboxes, send-on-behalf
- Calendar, interview scheduling, offer tracking
- Bulk auto-apply
- Review approve starting Auto-Apply (deliberately not wired)
- CAPTCHA / SSO walls on vendor apply pages
- Template-management UI beyond IDs and variables

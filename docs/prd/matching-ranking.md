# Matching & Ranking — Product Requirements

> **Runbook phase:** Phase 6 &nbsp;·&nbsp; **Feature key:** `matching-ranking`
>
> Consolidated PRD for the "Matching & Ranking" feature — combines the backend,
> database, and frontend requirements in one place. The canonical,
> CodeSpring-generated sources remain the source of truth:
> - [Backend PRD](../../.codespring/PRDs/matching-ranking/backend-prd-matching-ranking.md)
> - [Database PRD](../../.codespring/PRDs/matching-ranking/database-prd-matching-ranking.md)
> - [Frontend PRD](../../.codespring/PRDs/matching-ranking/frontend-prd-matching-ranking.md)

---

## Backend

### Backend PRD: Matching & Ranking
**Feature:** Matching & Ranking  
**Type:** backend

### Matching & Ranking

#### Feature overview
Compute an AI-driven match percentage between a user’s resume and a job description, combining keyword hits and semantic similarity. Persist only high-quality matches based on a user-configurable threshold. Provide a brief, human-readable explanation for the score and record model/parameters for reproducibility.

#### Scope & behavior
- Inputs
  - Resume: reference (resumeId in Blob Storage) or raw text (UTF-8). Max 100k chars; reject empty or non-text.
  - Job: reference (jobId in DB) or raw text. Max 100k chars; reject empty or non-text.
  - Options: threshold (0–100, optional), explanation (bool), mode (sync/async), topN for ranking.
- Scoring
  - Score range: 0–100 (float, 1 decimal).
  - Keyword score (0–100): case-insensitive; stopword-filtered; de-duplicated; includes exact term hits and normalized variants (stemming/lemmatization). Weighted fields: job title (x2), required skills (x1.5), responsibilities (x1), company/benefits (x0.25). Cap contribution per unique term to avoid repetition inflation.
  - Semantic score (0–100): cosine similarity between resume and job embeddings via Azure OpenAI. Normalize raw similarity to [0,100].
  - Final score: weighted sum default keyword:semantic = 0.4:0.6; weights are system-configurable (not user-editable) and versioned.
- Threshold & persistence
  - Threshold resolution: user-level setting in Cosmos (default 70). If request provides threshold, it overrides user default for this computation only.
  - Persist to Cosmos DB only when final score >= resolved threshold. Otherwise return result without persistence.
  - For batch/ranking, optionally filter out results below threshold when returning/persisting.
- Explanation summary
  - When requested, generate <= 500 chars summary highlighting top matched skills/requirements and major gaps. Must not include PII beyond resume/job content. Truncate without breaking words.
- Normalization & versioning
  - Persist: algorithmVersion, embeddingsModel, promptVersion (for explanation), keywordWeightsVersion, normalizationMethod, createdAt, data hashes (sha256 of input texts) for reproducibility.
  - Changes in any version create new immutable results; no in-place re-scoring.
- Permissions & security
  - Auth: Azure AD B2C JWT. Access restricted to the authenticated user’s resources (resume/job) only.
  - Rate limits: 60 sync calls/min/user; batch enqueues limited to 1,000 pairs/op.
  - PII: Do not log raw texts; redact in telemetry; store only hashes + minimal derived features when needed.
- Performance & reliability
  - Sync SLA target P50 < 3s, P95 < 8s for single pair.
  - Azure Functions Consumption timeout: move to async if expected > 20s.
  - Idempotency: optional Idempotency-Key header to dedupe within 24h (same inputs+options -> same matchId/response).
  - Queue retries: Storage Queue with poison queue after 5 attempts.

#### API
- POST /v1/matches/compute
  - Auth: Bearer token.
  - Body: { resumeId?|resumeText, jobId?|jobText, threshold?, explanation?: bool, mode?: "sync"|"async" }
  - Responses:
    - 200 (sync): { score, breakdown: { keyword, semantic, weights }, explanation?, persisted: bool, matchId?, thresholdUsed, versions: { algorithm, embeddingsModel, prompt, keywordWeights, normalization }, input: { resumeId?, jobId? } }
    - 202 (async): { operationId }
    - 400: validation errors; 401/403: auth; 413: payload too large.
  - Behavior: If mode=async or estimated cost > limits, enqueue {userId, inputs, options}; return 202.
- POST /v1/matches/rank
  - Auth: Bearer token.
  - Body: { resumeId?|resumeText, jobIds?: string[], jobTexts?: string[], topN?: number, threshold?, explanation?: bool, mode?: "async"|"sync" }
  - Responses:
    - 200: { results: [{ jobId?|idx, score, breakdown, explanation?, persisted }], topN applied, thresholdUsed, versions }
    - 202: { operationId }
  - Behavior: For N > 10, force async. Results sorted desc by score; if threshold provided, include only >= threshold when persisted; always return all computed scores unless client sets filterBelowThreshold=true.
- GET /v1/matches
  - Query: jobId?, resumeId?, minScore?, limit (<=100), cursor
  - Returns user-owned persisted matches with pagination.
- POST /v1/operations/{operationId}/cancel
  - Best-effort cancel if not yet dequeued.
- GET /v1/operations/{operationId}
  - Status: queued|running|completed|failed; if completed, return summary and where results stored.

#### Data model (Cosmos DB)
- MatchResult
  - id (GUID), userId, resumeRef {resumeId|textHash}, jobRef {jobId|textHash}
  - score, breakdown {keyword, semantic, weights}
  - explanation (optional, <= 500 chars)
  - thresholdUsed
  - versions {algorithmVersion, embeddingsModel, promptVersion, keywordWeightsVersion, normalizationMethod}
  - inputHashes {resumeSha256, jobSha256}
  - createdAt, source {sync|async|batch}, requestId
- UserSetting
  - userId (pk), matchThreshold (0–100, default 70)

#### User-facing flows
- Single compute (sync)
  - User submits resume/job → validate → compute keyword + embeddings → combine → optional explanation → compare to threshold → persist if met → return 200 with result and persisted flag.
- Batch ranking (async)
  - User submits resume + multiple jobs → request accepted (202) → messages enqueued → workers compute per pair → persist those >= threshold → operation completes → results retrievable via GET matches or operation details.

Edge cases:
- Empty or non-parseable text → 400 with code INVALID_INPUT.
- Extremely short inputs (<30 chars) → compute but flag low-confidence in telemetry; do not block.
- Identical resume/job hashes to an existing persisted result with same versions and options → return existing matchId (idempotent).
- Explanation generation failure → return score without explanation; do not fail match.

#### Acceptance criteria
- Combines keyword and semantic scores into a 0–100 final score with default weights 0.4/0.6.
- Respects per-request threshold override; otherwise uses user default; persists only when score >= threshold.
- Returns explanation <= 500 chars when requested; omission does not fail request.
- Records versions, weights, normalization, and input hashes on every persisted match.
- Sync endpoint completes within performance targets for single pair; auto-falls back to async when necessary.
- Enforces auth and ownership; users cannot access others’ matches/resumes/jobs.
- Idempotency returns same matchId for identical inputs/options within 24h when header provided.
- Batch rank returns scores sorted desc; forces async for N > 10 and handles up to 1,000 pairs/op.
- Validation errors, rate limits, and payload size limits return appropriate HTTP codes/messages.

#### Out of scope
- Resume parsing/OCR, job scraping/ingestion.
- UI/notifications.
- Learning-to-rank model training and weight auto-tuning.
- Cross-user or recruiter-facing features.
- Deduplication of semantically similar jobs beyond simple hashing.
---

## Database

### Database PRD: Matching & Ranking
**Feature:** Matching & Ranking  
**Type:** database

#### Feature Summary
Persist and audit AI-driven matching and ranking between a user’s resume and a job posting. Store keyword and semantic scores, normalized results, configurable save threshold, explanation summary, and model/version metadata for reproducibility.

#### Entities & Relationships
- match_runs: One record per evaluation of a resume–job pair for a user. References model_registry and embeds score components, normalization outputs, threshold used, and decision flags.
- match_explanations: Optional, detailed rationale linked 1:1 to a match_run. Stores summary text and structured highlights/gaps.
- user_match_prefs: Active per-user configuration controlling threshold and save policy.
- user_match_pref_history: Immutable audit trail of preference changes for reproducibility.
- model_registry: Versioned registry of models, prompt and formula versions, and normalization methods/params used during scoring.

#### Core Behaviors
- Keyword + semantic scoring are captured as both raw and normalized values. overall_score_pct is computed from normalized components using the formula_version tied to model_registry.
- Configurable threshold: At evaluation time, threshold_used is copied from user_match_prefs.threshold_pct (or request override if present) and meets_threshold is computed. decision_saved reflects whether the record should be retained based on save policy.
- Explanation summary: Store a brief explanation_summary on match_runs and optional detailed rationale in match_explanations, with overflow artifacts in Blob (explanation_blob_uri).
- Normalization & versioning: Store model_version_id and normalization_method/params reference in model_registry; persist all computed values and params to allow exact recomputation and comparison across runs.

#### Constraints & Data Rules
- overall_score_pct: 0–100 INT; keyword/semantic scores: 0.0–1.0 FLOAT.
- threshold_pct: 0–100 INT. meets_threshold = overall_score_pct >= threshold_used.
- One active user_match_prefs per user; changes create a new history row.
- Idempotency: idempotency_key unique per (user, resume, job, model/config) to prevent duplicate runs.
- Large artifacts (feature vectors, long explanations) must be stored in Blob; DB only stores references.

#### Indexing (Cosmos DB logical guidance)
- match_runs: composite on (user_id, job_id), (user_id, resume_id); filtered queries on meets_threshold and completed_at; unique on idempotency_key.
- match_explanations: partition by match_id.
- user_match_prefs: partition by user_id.
- model_registry: lookup by model_version_id and (ai_service, scorer_model, scorer_model_version, formula_version).

#### Edge Cases
- Missing or stale prefs: if none, use system default threshold 70 and save_all_matches=false; persist threshold_used.
- Model updates: new rows in model_registry; old runs remain tied to prior model_version_id.
- Re-runs: Allowed; distinguish via new match_id but same idempotency_key should be rejected with conflict.
- Errors: run_status='error' with error_message; decision_saved=false.

#### Retention
- match_runs and match_explanations retained for 18 months; blob URIs may expire independently and should be validated at read time.
---

## Frontend

### Frontend PRD: Matching & Ranking
**Feature:** Matching & Ranking  
**Type:** frontend

#### Feature overview
Display an AI-generated match percentage between a user’s resume and a job posting, combine keyword and semantic signals, and present a brief rationale. Allow users to configure a minimum match threshold that governs which results are flagged as “save-worthy” and persisted. Surface model/version info to ensure reproducibility and clarity when scores change.

#### Scope & behavior
- Match score display
  - Normalized 0–100%, integer by default (e.g., 82%). Optional single-decimal on hover tooltip.
  - Color states: 0–49 red, 50–69 amber, 70–100 green. Do not rely on color alone; include label (e.g., “Good match”).
  - States: loading (skeleton badge), computed, error (dash “—” with tooltip).
- Keyword + Semantic scoring overview
  - Tooltip/expand shows weighted breakdown: “Keywords 40% • Semantic 60%” and top 5 matched entities/phrases.
  - Chip group: up to 6 highlighted keywords/phrases; remaining collapsed under “+X more.”
- Explanation summary
  - Collapsible section “Why this score” with a 2–4 sentence rationale.
  - Truncate at 600 chars with “Show more” to expand up to 2000 chars. Preserve line breaks.
- Configurable threshold
  - User setting (default 70%). Slider (0–100) + numeric input. Changes persist immediately.
  - Threshold affects UI badges (“≥ threshold” shows “Meets Threshold” tag) and determines which matches are auto-saved/prompted to save.
  - On job lists: optional filter toggle “Only show ≥ threshold.”
  - Threshold is per-user; read-only for non-authenticated users (hide control).
- Normalization & versioning
  - Info icon reveals: model name, version, profile, last computed timestamp (UTC), and normalization range (0–100%).
  - If a score was computed with an older model, show subtle “Outdated” pill with tooltip “Recomputed with vX.Y may differ.”
- Error/edge validations
  - If resume missing: show neutral score state with CTA “Add resume to see match.”
  - If job text insufficient: show “Not enough data to score.”
  - Network/compute error: retry button; non-blocking for page interactions.
- Permissions
  - Available to signed-in job seekers. Threshold setting gated to authenticated users.

#### User-facing flows
- Job list
  - Each job card shows: Match badge (percent + color + label), Meets Threshold tag if applicable.
  - Hover/click on badge opens breakdown tooltip. Clicking “Why this score” opens side panel/modal with full explanation summary.
  - “Only show ≥ threshold” toggle filters list client-side (when scores are available).
- Job detail
  - Prominent match meter (circular or bar), percentage, label, Meets Threshold tag.
  - Explanation section collapsed by default. “View model/version” info icon near the meter.
  - If ≥ threshold: auto-select “Save match” checkbox; otherwise unchecked. User can override.
- Settings > Matching
  - Slider + numeric input (0–100). Input validates integers 0–100; out-of-range shows inline error, disables Save.
  - Save feedback: inline success “Threshold updated.”

#### Acceptance criteria
- Scores render as integers 0–100; color and textual label align with ranges.
- Tooltip shows keyword/semantic weights and up to 5 top terms; overflow grouped.
- Explanation summary truncates to 600 chars with “Show more”; expands smoothly; ESC closes modal/panel.
- Threshold changes persist and immediately update Meets Threshold tags across current views.
- List filter hides items below threshold without layout shift jank (use height placeholders while filtering).
- Missing resume shows neutral state with CTA; no percentage displayed.
- Model/version info visible via info icon; outdated scores show “Outdated” pill.
- All interactive elements keyboard accessible (Tab/Shift+Tab), focus-visible, tooltips on focus and hover.
- Contrast ratio ≥ 4.5:1; color not sole indicator of state.
- Loading uses skeletons for badge and meter; errors show tooltip and retry.

#### Out of scope
- Backend scoring algorithms, weight tuning, or re-computation scheduling.
- Resume parsing/editing and job content enrichment.
- Notifications or recommendations driven by match changes.
- Team/org-level threshold policies or A/B experiments.
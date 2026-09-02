# Backend PRD: Matching & Ranking
**Feature:** Matching & Ranking  
**Type:** backend

# Matching & Ranking

## Feature overview
Compute an AI-driven match percentage between a user’s resume and a job description, combining keyword hits and semantic similarity. Persist only high-quality matches based on a user-configurable threshold. Provide a brief, human-readable explanation for the score and record model/parameters for reproducibility.

## Scope & behavior
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

## API
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

## Data model (Cosmos DB)
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

## User-facing flows
- Single compute (sync)
  - User submits resume/job → validate → compute keyword + embeddings → combine → optional explanation → compare to threshold → persist if met → return 200 with result and persisted flag.
- Batch ranking (async)
  - User submits resume + multiple jobs → request accepted (202) → messages enqueued → workers compute per pair → persist those >= threshold → operation completes → results retrievable via GET matches or operation details.

Edge cases:
- Empty or non-parseable text → 400 with code INVALID_INPUT.
- Extremely short inputs (<30 chars) → compute but flag low-confidence in telemetry; do not block.
- Identical resume/job hashes to an existing persisted result with same versions and options → return existing matchId (idempotent).
- Explanation generation failure → return score without explanation; do not fail match.

## Acceptance criteria
- Combines keyword and semantic scores into a 0–100 final score with default weights 0.4/0.6.
- Respects per-request threshold override; otherwise uses user default; persists only when score >= threshold.
- Returns explanation <= 500 chars when requested; omission does not fail request.
- Records versions, weights, normalization, and input hashes on every persisted match.
- Sync endpoint completes within performance targets for single pair; auto-falls back to async when necessary.
- Enforces auth and ownership; users cannot access others’ matches/resumes/jobs.
- Idempotency returns same matchId for identical inputs/options within 24h when header provided.
- Batch rank returns scores sorted desc; forces async for N > 10 and handles up to 1,000 pairs/op.
- Validation errors, rate limits, and payload size limits return appropriate HTTP codes/messages.

## Out of scope
- Resume parsing/OCR, job scraping/ingestion.
- UI/notifications.
- Learning-to-rank model training and weight auto-tuning.
- Cross-user or recruiter-facing features.
- Deduplication of semantically similar jobs beyond simple hashing.
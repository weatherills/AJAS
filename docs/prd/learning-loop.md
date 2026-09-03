# Learning Loop — Product Requirements

> **Runbook phase:** Phase 8 &nbsp;·&nbsp; **Feature key:** `learning-loop`
>
> Consolidated PRD for the "Learning Loop" feature — combines the backend,
> database, and frontend requirements in one place. The canonical,
> CodeSpring-generated sources remain the source of truth:
> - [Backend PRD](../../.codespring/PRDs/learning-loop/backend-prd-learning-loop.md)
> - [Database PRD](../../.codespring/PRDs/learning-loop/database-prd-learning-loop.md)
> - [Frontend PRD](../../.codespring/PRDs/learning-loop/frontend-prd-learning-loop.md)

---

## Backend

### Backend PRD: Learning Loop
**Feature:** Learning Loop  
**Type:** backend

Feature overview
Learning Loop captures user approval/rejection decisions on job recommendations and uses them to tune per-user matching weights and display thresholds. It also produces lightweight precision/recall proxies over time to quantify impact. The goal is to personalize recommendations while maintaining measurable quality, without blocking the core user experience.

Scope & behavior
- In-scope entities
  - DecisionLog: approve/reject + optional free-text comment tied to a recommendation at a given model version and score.
  - ModelParams: per-user weights and a score_threshold used by the AI Matching Service.
  - Metrics: daily/weekly aggregates of precision/recall proxies.
- Persistence
  - Cosmos DB containers:
    - decisions (pk: user_id): decision_id, user_id, recommendation_id, job_id, decision {approve|reject}, comment, score_at_decision, features_snapshot_ref, model_version, created_at, idempotency_key.
    - model_params (pk: user_id): user_id, weights (map<string,float>), score_threshold (float), model_version, status {active|staged}, effective_at, updated_at, source {global|personalized}, sample_size.
    - metrics (pk: user_id#period): period_start, period_end, user_id|null, approvals, rejections, suggestions_shown, precision_proxy, recall_proxy, at_k (k=3,10) precision, threshold, model_version.
  - Blob Storage: features snapshots (JSON) keyed by recommendation_id for audit.
- Queues
  - learning-decisions (Storage Queue): enqueue immutable decision events for async aggregation/tuning.
  - tuning-tasks: internal tasks for batch/forced tuning jobs.

API endpoints (Azure Functions, HTTP-triggered v1)
- POST /v1/decisions
  - Auth: end-user (AAD B2C) with user_id in token; may only submit for self.
  - Body: { recommendation_id (req), job_id (req), decision (approve|reject, req), comment (<=1000 chars, optional), model_version (req), score_at_decision (0..1, req), idempotency_key (UUID, req) }
  - Responses: 201 Created { decision_id } | 200 OK if idempotent replay | 400 validation error | 404 unknown recommendation_id.
  - Behavior: write to Cosmos decisions (idempotent on user_id+idempotency_key), enqueue event to learning-decisions.
- GET /v1/learning/params?user_id=self
  - Auth: end-user; returns their active/staged ModelParams.
  - Response: { weights (redacted keys permitted), score_threshold, model_version, source, updated_at, sample_size }.
- POST /v1/learning/tune
  - Auth: admin/service only.
  - Body: { user_id|null, window_days (default 30), min_samples (default 20), force_activate (bool, default false) }
  - Behavior: enqueues tuning-tasks; immediate 202 Accepted.
- GET /v1/metrics?scope=self|global&period=7d|30d
  - Auth: end-user (self) or admin (global).
  - Response: list of period buckets with fields from metrics container.

Business logic and workflows
- Decision Logging
  - Validate recommendation_id belongs to user and is not expired (>90 days). Reject if stale.
  - Comments stored encrypted at rest; trimmed; UTF-8; block >1000 chars; allow empty.
  - Duplicate protection via idempotency_key per user.
- Weight/Threshold Tuning (asynchronous)
  - Trigger: daily scheduled job per user or when user accrues ≥N new decisions since last tune (default N=10), or admin-triggered.
  - Eligibility: require ≥min_samples (default 20) decisions in window_days; otherwise retain global defaults with source=global.
  - Adjustment policy (contractual outcomes, not implementation details):
    - Produce updated weights map and score_threshold that increase approval rate while keeping suggestions_shown above a minimum floor (default 10/week).
    - Cap per-cycle change: |Δweight_i| ≤ 0.2, |Δthreshold| ≤ 0.05 to avoid thrash.
    - If precision_proxy drops >10% over prior period, roll back to previous params and mark status=active, source=global.
  - Versioning: bump model_version; write staged params; atomically activate and notify AI Matching Service (internal service bus/event) to refresh caches.
- Basic Metrics
  - Precision proxy: approvals / (approvals + rejections) among surfaced recommendations above active threshold within period.
  - Recall proxy (coverage proxy): count_surfaced_above_threshold / count_scored_above_min_score (min_score=0.2) within period.
  - at_k precision: approvals where item ranked ≤k divided by items shown at ≤k.
  - Store per-user and global aggregates daily; expose rolling periods via API.

Security and permissions
- OAuth2/JWT via Azure AD B2C for end-users; Azure AD app role for admin/service.
- Data isolation by user_id; all Cosmos queries scoped to caller unless admin.
- PII: comments encrypted; access logged.
- Rate limits: POST /v1/decisions ≤ 10 req/sec/user; reject 429 with Retry-After.

Performance & reliability
- POST /v1/decisions p95 ≤ 300 ms (excluding async).
- Exactly-once semantics via idempotency_key; queue processing at-least-once with idempotent consumers.
- Cosmos RU budget: design to ≤ 5 RU/write typical; batch metrics updates.

User-facing flows
- User sees a recommendation, clicks Approve/Reject, optionally adds a comment. Client calls POST /v1/decisions. Success is immediate; UI updates without waiting for tuning.
- After enough decisions, tuning runs asynchronously; new params activated; subsequent recommendation fetches use updated weights/threshold automatically.
- Users or admins can query metrics and current params.

Edge cases
- Duplicate submission: same idempotency_key returns 200 with original decision_id.
- Unknown or stale recommendation_id: 404.
- Insufficient data for tuning: return 202 Accepted for tune request; no change to params; source remains global.
- User data deletion request: cascade delete decisions, params, metrics for user_id and blobs.

Acceptance criteria
- Logging a decision with valid payload persists to Cosmos, enqueues one event, and returns 201/200 in ≤300 ms p95.
- Idempotent replay with same idempotency_key does not create duplicate records or queue messages.
- Tuning does not activate personalized params unless min_samples met; otherwise retains global defaults.
- After activation, AI Matching Service receives parameter update event within 60 seconds.
- Metrics endpoint returns precision_proxy and recall_proxy consistent with stored decisions for the requested period.
- Comments >1000 chars are rejected with 400; stored comments are encrypted at rest.
- Non-admin cannot trigger /v1/learning/tune nor read global metrics; admin can query global metrics and any user’s params.
- Rollback occurs automatically if precision_proxy degrades >10% vs prior period; previous params restored and logged.

Out of scope
- Frontend UI for capturing decisions or displaying metrics.
- Advanced model training beyond weight/threshold adjustments.
- Cross-user collaborative tuning, A/B testing framework, or multi-armed bandits.
- External application outcome feedback (e.g., interview offers).
---

## Database

### Database PRD: Learning Loop
**Feature:** Learning Loop  
**Type:** database

##### Feature Summary
Learning Loop stores user decisions on AI job-match recommendations, versions weight/threshold configurations, and tracks basic precision/recall proxies over time to inform iterative tuning.

##### Scope & Behavior
- Decision Logging
  - Persist a recommendation snapshot at generation time with score, score components, and weight_config_id/threshold used.
  - Persist exactly one decision per recommendation per user: approve/reject/skip with optional comment and client metadata.
  - Decisions capture the effective score and threshold used at the time of decision for auditability.
  - Recommendations may expire; expired items cannot accept new decisions.
- Weight/Threshold Tuning
  - Store immutable, versioned weight configurations (JSON of feature weights + a global threshold).
  - Record tuning events that link old/new configs with diffs, reason, and whether manual or auto-triggered.
  - Only one active weight_config at a time; new active config supersedes the previous.
- Basic Metrics
  - Periodic metric snapshots over a time window and scope (global, user segment, or user).
  - Store counts: recommendations, decisions, approves, rejects, skips, and TP/FP/FN proxies.
  - Persist derived precision/recall to freeze historical views and support trend analysis.

##### Entities & Relationships
- recommendations (1) —< decision_log (0..1 per recommendation_id per user_id)
- weight_config (versioned catalog) — tuning events link old -> new
- metrics_snapshot references the weight_config in effect during the window

##### Constraints
- One decision per (recommendation_id, user_id); updates overwrite in place (track updated_at).
- recommendation.status transitions: pending -> decided or expired. Deciding an expired recommendation is rejected at the app layer.
- weight_config.is_active: at most one row true; new active config should reference superseded config.
- recommendation.recommended is computed at generation using score >= threshold to preserve historical context.

##### Indexing & Partitioning (Cosmos DB guidance)
- Partition keys:
  - recommendations: /user_id (high cardinality, decision affinity)
  - decision_log: /user_id (co-locate with recommendations for RUs efficiency)
  - metrics_snapshot: /scope_ref ("global", segment key, or user_id)
  - weight_config & weight_tuning_event: /weight_config_id and /tuning_event_id respectively (low write volume)
- Suggested indexes:
  - recommendations: user_id+generated_at DESC, weight_config_id, status
  - decision_log: user_id+decided_at DESC, recommendation_id
  - metrics_snapshot: weight_config_id+window_end DESC, scope_type+scope_ref

##### Data Quality & Edge Cases
- Immutable recommendation snapshot fields (score, score_components, weight_config_id, threshold) must not change after creation.
- If a user attempts multiple decisions, last-write wins while maintaining uniqueness; updated_at records modifications.
- Skips count as negatives in recall proxy but are excluded from precision by default; compute policies captured in metrics_snapshot notes if needed.
- Orphan prevention: decisions require existing recommendations; tuning events require valid old/new configs.

---

## Frontend

### Frontend PRD: Learning Loop
**Feature:** Learning Loop  
**Type:** frontend

### Learning Loop — Frontend PRD

#### Feature overview
Enable users to provide explicit feedback on AI job matches (approve/reject with optional comments) and visualize how the system adapts over time. Provide a simple control for match strictness (manual or auto-tuned) and a lightweight metrics view to build trust and transparency. All interactions are per-user and affect future match ranking only.

#### Scope & behavior
- Surfaces
  - On Match List/Detail: Approve and Reject actions with optional comment capture.
  - Preferences → Matching: “Tuning mode” and “Match strictness” control.
  - Learning panel: Basic metrics over time with status of auto-tuning.
- States
  - Actions: idle, submitting, success (with 5s undo), error (retry).
  - Metrics: loading, loaded (with data), empty (no decisions), error.
  - Tuning: Auto (read-only strictness + info text), Manual (editable strictness).
- Validations
  - Comments optional; max 500 chars; trimmed; block submission of only whitespace.
  - One decision per match per user; subsequent clicks on the same match replace the prior decision (with confirm modal).
  - Strictness slider yields discrete levels: Conservative (0), Balanced (1), Adventurous (2).
- Errors
  - Network/API failure: non-blocking toast with “Retry” and preserves local state for 30 min to re-send.
  - Comment save failure does not revert the decision; show inline warning on the comment field.
- Permissions
  - Authenticated users only. All UI hidden for signed-out users.
- Accessibility
  - Approve/Reject are buttons with aria-labels, visible focus states, and keyboard operable (Tab + Space/Enter).
  - Undo exposed as a button, not only toast text. Color use paired with icon/text.
  - Metrics charts include textual summaries for screen readers.

#### User-facing flows
- Decision Logging
  1. User clicks Approve or Reject on a match card or detail.
  2. Inline comment input expands (optional). User may type and hit Save, or dismiss.
  3. UI sends decision event; optimistic state applied (badge on card + subdued opposite action).
  4. Success: show toast “Recorded. Undo” (5s). Undo reverts local state and sends reversal event.
  5. Error: revert optimistic state, show error toast with Retry. Retry resubmits last payload.
  - Edge cases:
    - Double-clicks coalesced; disable buttons while submitting.
    - Changing decision later prompts: “Replace your previous decision?” [Replace/Cancel].
- Weight/Threshold Tuning
  1. Preferences → Matching.
  2. Tuning mode: Auto (default) or Manual.
     - Auto: strictness slider is disabled; helper text “Adjusted from your last 30 decisions.”
     - Manual: slider enabled; selecting level shows preview helper “Fewer matches, higher precision” (Conservative) / “Balanced” / “More matches, higher recall” (Adventurous).
  3. Save shows non-blocking confirmation “Preferences updated. Takes effect on new suggestions.”
  - Edge cases:
    - No decisions yet in Auto: banner “We’ll adapt after your first few choices.”
- Basic Metrics
  - Panel on Dashboard and within Preferences:
    - Approve rate (last 7d)
    - Decision volume (last 7d)
    - Trend sparkline of approve rate (7d) with % delta vs prior 7d
    - “Exposure strictness” current level and whether Auto or Manual
  - Empty state: “No learning signals yet. Start by reviewing matches.”
  - Time range toggle: 7d (default) / 30d persists in local storage.

#### Acceptance criteria
- Approve/Reject buttons render on every match card/detail when signed in; hidden when signed out.
- Clicking Approve/Reject updates the card to show selected state, disables both buttons during submit, and shows undo toast on success.
- Optional comment input supports up to 500 visible characters and prevents whitespace-only submission.
- Re-deciding on the same match triggers a confirm modal; choosing Replace updates UI and logs new decision.
- Errors surface via toast; Retry resubmits and restores optimistic state on success.
- Preferences screen shows Auto (default) with disabled slider; switching to Manual enables slider with three discrete labeled stops.
- Saving preferences updates the visible strictness indicator across UI and persists across sessions.
- Metrics panel loads asynchronously; shows correct zero state when the user has no decisions; includes textual summary for screen readers.
- Keyboard and screen reader users can operate all decision controls, Undo, and preferences without a mouse.

#### Out of scope
- Displaying raw model weights or exact thresholds.
- Team/organizational aggregation or leaderboards.
- Advanced analytics (ROC curves, per-feature attribution).
- Editing or deleting historical comments beyond immediate Undo window.
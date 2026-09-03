# Database PRD: Matching & Ranking
**Feature:** Matching & Ranking  
**Type:** database

## Feature Summary
Persist and audit AI-driven matching and ranking between a user’s resume and a job posting. Store keyword and semantic scores, normalized results, configurable save threshold, explanation summary, and model/version metadata for reproducibility.

## Entities & Relationships
- match_runs: One record per evaluation of a resume–job pair for a user. References model_registry and embeds score components, normalization outputs, threshold used, and decision flags.
- match_explanations: Optional, detailed rationale linked 1:1 to a match_run. Stores summary text and structured highlights/gaps.
- user_match_prefs: Active per-user configuration controlling threshold and save policy.
- user_match_pref_history: Immutable audit trail of preference changes for reproducibility.
- model_registry: Versioned registry of models, prompt and formula versions, and normalization methods/params used during scoring.

## Core Behaviors
- Keyword + semantic scoring are captured as both raw and normalized values. overall_score_pct is computed from normalized components using the formula_version tied to model_registry.
- Configurable threshold: At evaluation time, threshold_used is copied from user_match_prefs.threshold_pct (or request override if present) and meets_threshold is computed. decision_saved reflects whether the record should be retained based on save policy.
- Explanation summary: Store a brief explanation_summary on match_runs and optional detailed rationale in match_explanations, with overflow artifacts in Blob (explanation_blob_uri).
- Normalization & versioning: Store model_version_id and normalization_method/params reference in model_registry; persist all computed values and params to allow exact recomputation and comparison across runs.

## Constraints & Data Rules
- overall_score_pct: 0–100 INT; keyword/semantic scores: 0.0–1.0 FLOAT.
- threshold_pct: 0–100 INT. meets_threshold = overall_score_pct >= threshold_used.
- One active user_match_prefs per user; changes create a new history row.
- Idempotency: idempotency_key unique per (user, resume, job, model/config) to prevent duplicate runs.
- Large artifacts (feature vectors, long explanations) must be stored in Blob; DB only stores references.

## Indexing (Cosmos DB logical guidance)
- match_runs: composite on (user_id, job_id), (user_id, resume_id); filtered queries on meets_threshold and completed_at; unique on idempotency_key.
- match_explanations: partition by match_id.
- user_match_prefs: partition by user_id.
- model_registry: lookup by model_version_id and (ai_service, scorer_model, scorer_model_version, formula_version).

## Edge Cases
- Missing or stale prefs: if none, use system default threshold 70 and save_all_matches=false; persist threshold_used.
- Model updates: new rows in model_registry; old runs remain tied to prior model_version_id.
- Re-runs: Allowed; distinguish via new match_id but same idempotency_key should be rejected with conflict.
- Errors: run_status='error' with error_message; decision_saved=false.

## Retention
- match_runs and match_explanations retained for 18 months; blob URIs may expire independently and should be validated at read time.
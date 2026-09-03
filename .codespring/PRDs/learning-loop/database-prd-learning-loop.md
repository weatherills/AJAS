# Database PRD: Learning Loop
**Feature:** Learning Loop  
**Type:** database

### Feature Summary
Learning Loop stores user decisions on AI job-match recommendations, versions weight/threshold configurations, and tracks basic precision/recall proxies over time to inform iterative tuning.

### Scope & Behavior
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

### Entities & Relationships
- recommendations (1) —< decision_log (0..1 per recommendation_id per user_id)
- weight_config (versioned catalog) — tuning events link old -> new
- metrics_snapshot references the weight_config in effect during the window

### Constraints
- One decision per (recommendation_id, user_id); updates overwrite in place (track updated_at).
- recommendation.status transitions: pending -> decided or expired. Deciding an expired recommendation is rejected at the app layer.
- weight_config.is_active: at most one row true; new active config should reference superseded config.
- recommendation.recommended is computed at generation using score >= threshold to preserve historical context.

### Indexing & Partitioning (Cosmos DB guidance)
- Partition keys:
  - recommendations: /user_id (high cardinality, decision affinity)
  - decision_log: /user_id (co-locate with recommendations for RUs efficiency)
  - metrics_snapshot: /scope_ref ("global", segment key, or user_id)
  - weight_config & weight_tuning_event: /weight_config_id and /tuning_event_id respectively (low write volume)
- Suggested indexes:
  - recommendations: user_id+generated_at DESC, weight_config_id, status
  - decision_log: user_id+decided_at DESC, recommendation_id
  - metrics_snapshot: weight_config_id+window_end DESC, scope_type+scope_ref

### Data Quality & Edge Cases
- Immutable recommendation snapshot fields (score, score_components, weight_config_id, threshold) must not change after creation.
- If a user attempts multiple decisions, last-write wins while maintaining uniqueness; updated_at records modifications.
- Skips count as negatives in recall proxy but are excluded from precision by default; compute policies captured in metrics_snapshot notes if needed.
- Orphan prevention: decisions require existing recommendations; tuning events require valid old/new configs.

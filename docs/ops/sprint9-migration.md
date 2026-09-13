# Sprint 8 → Sprint 9 migration

Sprint 9 adds matching explainability, job enrichment, email intent, and operator
flags on top of the Sprint 8 Graph / Auto-Apply / Review work. No Cosmos container
rename is required. New fields are optional and ignored by older readers.

## What changed

- Match compute/rank responses include `evidence` (top 5 sentences), `bucket`,
  `gate` (must-have coverage), `highlights`/`gaps`, and `features` for
  learning-to-rank logs (`ajas.match.ltr`).
- Job feed cards may include `workplace`, `seniority`, `salaryMin`/`salaryMax`.
  Missing values mean “unknown”; the UI does not hide those rows.
- Email messages include `intent` (`interview` | `rejection` | `follow_up` |
  `generic`). Recruiter templates `interested`, `not_fit`, and `schedule` are
  extra system templates.
- Health/ready expose `workers`, `dependencies`, `flags`, and `imap` (Graph-only;
  IMAP stays off).
- Feature flags default **off** for Indeed/LinkedIn adapters, IMAP, and bulk
  Auto-Apply. Those adapters ingest **fixtures only**; they do not scrape HTML.

## Env flags

| Setting | Default | Purpose |
| --- | --- | --- |
| `FLAG_INDEED_ADAPTER` | false | Load Indeed JSON fixtures |
| `FLAG_LINKEDIN_ADAPTER` | false | Load LinkedIn JSON fixtures |
| `FLAG_SITE_POLICY_CONSENT` | false | Required before any optional board HTTP |
| `FLAG_RESPECT_ROBOTS` | true | Fail closed on robots.txt |
| `FLAG_IMAP_TRANSPORT` | false | IMAP remains unimplemented |
| `FLAG_BULK_AUTO_APPLY` | false | Bulk apply still confirms per job |
| `FLAG_LTR_LOGGING` | true | Feature vectors in match logs |
| `FLAG_DATA_RETENTION_PURGE` | true | Stale job/email purge planner |
| `JOB_RETENTION_DAYS` | 120 | Job inactivity window |
| `OUTBOUND_ALLOWLIST` | Greenhouse/Lever/Graph hosts | Outbound HTTP hosts |

## Operator commands

```
python scripts/rebuild_taxonomy.py
python scripts/reindex_embeddings.py
python scripts/seed_demo.py
```

## Rollback

Unset the new `FLAG_*` env vars. Clients that ignore unknown JSON fields keep
working. Match explanations remain ≤500 characters as in Sprint 8.

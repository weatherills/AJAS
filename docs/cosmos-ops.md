# Cosmos operations: RU, geo, keys, backfill, archive

Companion to [`db-setup.md`](db-setup.md) and [`cosmos.schema.md`](cosmos.schema.md).

## Capacity and autoscale

Default is **serverless**. To run provisioned autoscale:

```bash
COSMOS_THROUGHPUT_MODE=autoscale COSMOS_AUTOSCALE_MAX_RU=4000
```

Hot containers (`matches`, `resumes`, `auto_apply_attempts`, `job_postings_canonical`, `email_threads`, `user_settings`) get the full max RU; others get `max/4`. Daily budget `COSMOS_DAILY_RU_BUDGET` (default 250000) fires `cosmos.daily_ru`. IaC: `infra/cosmos-autoscale.bicep`.

## Query lint

`CosmosDAL.query` fails closed on cross-partition scans unless the container is a tiny catalog or `allow_cross_partition=True`. Remediation: pass `partition_key=`, add a composite (see index tuner), or allowlist only catalogs with <10 docs.

```bash
python scripts/tune_cosmos_indexes.py
```

## Consistency

`COSMOS_CONSISTENCY` overrides every container (Session/Strong). Defaults: **Strong** for `user_settings`, `email_connections`, `submit_requests`, `schema_migrations`; **Session** elsewhere. Hot paths use the same session/partition for read-your-writes.

## Geo and failover

Set `COSMOS_PREFERRED_REGIONS=eastus,westus`. RPO is 0 for session reads after failover; RTO target is 60s. Drill: `failover_drill(from_region=..., to_region=..., elapsed_seconds=...)`.

## Key rotation

Quarterly. Rotate the secondary Cosmos key in the portal, set `COSMOS_KEY`, then:

```python
from app.storage.key_rotation import rotate_cosmos_key
rotate_cosmos_key(new_key, previous=old_key)  # clears CosmosClient cache
```

Verify `/api/health` and a matches list. Swap primary/secondary, delete the old key. Reminder: calendar every 90 days.

## PII

Client-side seal for token fields (`email_connections.access_token_enc`). DAL `read(..., redact=True)` / `query(..., redact=True)` masks emails and filenames. Analytics export always scrubs.

## Backfill v2

```bash
python scripts/cosmos_backfill.py --container matches --dry-run
```

Chunks of 50, stops if the run exceeds the RU budget.

## Analytics and archive

Nightly JSONL export of durable rows with PII masked. Cold path: `cosmos-archive` blob container; restore via `restore_from_jsonl`.

## SDK canary

Pin `azure-cosmos==4.17.1`. Canary imports the SDK and runs FakeDatabase CRUD. Rollback: revert the pin in `backend/requirements.txt` and redeploy.

## Chaos and load

Inject 429/503 via `app.storage.chaos`. Synthetic load: `python -c "from app.storage.loadtest import run_load; print(run_load())"`.

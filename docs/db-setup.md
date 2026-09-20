# Database setup, bootstrap, and troubleshooting

AJAS uses Azure Cosmos DB (serverless) plus Azure Blob Storage and Storage Queues.
Local development uses Azurite and, optionally, the Linux Cosmos emulator.

## Environment

Copy `.env.sample` and never commit secrets.

| Variable | Local | Production |
|---|---|---|
| `COSMOS_CONNECTION_STRING` | Emulator / CI key | unset |
| `COSMOS_ENDPOINT` | `https://localhost:8081` | account URI |
| `COSMOS_KEY` | emulator key only | unset |
| `COSMOS_DATABASE` | `ajas` | `ajas` |
| `BLOB_CONNECTION_STRING` | `UseDevelopmentStorage=true` | unset |
| `BLOB_ACCOUNT_URL` | unset | `https://<acct>.blob.core.windows.net` |
| `QUEUE_CONNECTION_STRING` | `UseDevelopmentStorage=true` | unset |
| `QUEUE_ACCOUNT_URL` | unset | `https://<acct>.queue.core.windows.net` |
| `KEY_VAULT_URI` | unset | Key Vault for remaining secrets |

Cloud uses **DefaultAzureCredential** (managed identity) when an endpoint / account URL is set and no connection string is present. Provision output and logs never print keys.

## Emulators

```bash
docker compose up azurite            # Blob :10000  Queue :10001  Table :10002
docker compose --profile cosmos up   # Cosmos emulator :8081 (optional, heavy)
```

Azurite is enough for queue/blob tests. Cosmos unit tests use an in-memory `FakeDatabase` unless `COSMOS_CONNECTION_STRING` is set.

## Bootstrap / migrate / seed

Idempotent. Safe to re-run.

```bash
python scripts/provision_storage.py --dry-run          # plan only
python scripts/provision_storage.py --blobs --queues   # Azurite
python scripts/provision_storage.py --cosmos --migrate # live Cosmos
python scripts/provision_storage.py --seed
python scripts/migrate_storage.py                      # containers + sprocs/UDFs/triggers
```

Schema version is `ajas.cosmos.v1`, stored in `schema_migrations`. Throughput is **serverless** (no dedicated RU on create). Stored logic lives in `backend/app/storage/scripts/` (`sp_safeUpsert`, `udf_avgScore`, `trg_setTimestamps`, `trg_enqueueHint`).

## Backup / restore

Durable containers (applications, matches, decisions, settings) export as JSONL:

```bash
python scripts/backup_storage.py export --dest var/backup
python scripts/backup_storage.py import --dest var/backup
```

## Common failures

- **Azurite connection refused** — start compose or `azurite`; check ports 10000/10001.
- **Cosmos TLS / emulator cert** — the Linux emulator uses a self-signed cert; set `COSMOS_CONNECTION_STRING` from the emulator output, or skip live Cosmos and use FakeDatabase.
- **409 unique key** — unique keys are per partition and omit the partition-key path. Re-seed is upsert-safe; colliding `idempotency_key` / `graph_message_id` means a real duplicate.
- **429 throttling** — DAL retries 429/408/503 with backoff and increments `cosmos.throttles`. Ops alerts fire at 5 throttles or 4000 RU/s.
- **Poison queue growth** — `{queue}-poison` plus ops `queue.dlq_depth` (threshold 1). Inspect DLQ, fix schema, replay.
- **Stale schemaVersion** — `sp_safeUpsert` / `safe_upsert_document` reject writes with a lower version than the stored document.
- **Etag mismatch** — replace with `If-Match` failed; re-read and retry.

See `docs/cosmos.schema.md` for containers, partition keys, TTL, unique keys, RU notes, API/DAL mapping, consistency, and ownership. Operations (autoscale, lint, keys, backfill, archive): `docs/cosmos-ops.md`.

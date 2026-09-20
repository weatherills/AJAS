# Data plane

AJAS persists Review, Matching, Resumes, Jobs, Mail, Auto-Apply, Settings, and Learning
data on Cosmos DB (serverless), Azure Blob Storage, and Storage Queues.

## Identity

- Local: connection strings (Azurite `UseDevelopmentStorage=true`, Cosmos emulator).
- Cloud: prefer `DefaultAzureCredential` from `azure-identity` plus Key Vault.
  Set `KEY_VAULT_URI`; `app.secrets.hydrate_from_key_vault()` loads secrets at process start.
- Never log OAuth tokens. Settings stores `access_token_enc` / `refresh_token_enc` encrypted.

## Environment

See `.env.sample`. Functions read the same names from `local.settings.json` / app settings.

| Variable | Purpose |
|---|---|
| `COSMOS_CONNECTION_STRING` | Cosmos SDK; empty keeps in-memory feature stores |
| `COSMOS_DATABASE` | Database id (`ajas`) |
| `BLOB_CONNECTION_STRING` | Blob (Azurite or Azure) |
| `QUEUE_CONNECTION_STRING` | Storage Queues |
| `KEY_VAULT_URI` | Optional secret source |

## Provision

```bash
python scripts/provision_storage.py --dry-run --seed
docker compose up -d azurite
```

Containers, partition keys, TTL, and indexes: [cosmos.schema.md](cosmos.schema.md).
Local emulators: [local-emulators.md](local-emulators.md).
HTTP contract: [endpoint-contract.md](endpoint-contract.md).

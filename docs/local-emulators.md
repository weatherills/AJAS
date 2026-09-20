# Local emulators

## Azurite (Blob + Queue + Table)

```bash
docker compose up -d azurite
# or: npx azurite --silent --location /tmp/azurite
```

Env:

```
BLOB_CONNECTION_STRING=UseDevelopmentStorage=true
QUEUE_CONNECTION_STRING=UseDevelopmentStorage=true
```

Ports: blob `10000`, queue `10001`, table `10002`.

## Cosmos emulator (optional)

The Linux emulator image is large. Enable the compose profile only when you need a real account:

```bash
docker compose --profile cosmos up -d
```

Then set `COSMOS_CONNECTION_STRING` to the emulator connection string (HTTPS `localhost:8081`, disable TLS verify for local SDK clients) and run:

```bash
python scripts/provision_storage.py --cosmos --blobs --queues --seed
```

Without Cosmos, feature stores stay in-memory; the shared `CosmosDAL` tests use an in-process fake.

#!/usr/bin/env bash
# Per-boot startup for AJAS. Brings up the Azurite storage emulator (Azure
# Blob/Queue/Table) that the backend pipelines depend on. Idempotent: it will
# not start a second instance if one is already listening, and it returns once
# the emulator is ready.
set -euo pipefail

export PATH="$HOME/.npm-global/bin:$PATH"

AZURITE_DIR="$HOME/.azurite"
AZURITE_LOG="$HOME/.azurite/azurite.log"
BLOB_PORT=10000
QUEUE_PORT=10001
TABLE_PORT=10002

mkdir -p "$AZURITE_DIR"

port_open() {
  (echo > "/dev/tcp/127.0.0.1/$1") >/dev/null 2>&1
}

if port_open "$BLOB_PORT"; then
  echo "Azurite already running on port $BLOB_PORT; nothing to do."
  exit 0
fi

if ! command -v azurite >/dev/null 2>&1; then
  echo "azurite not found on PATH; run .cursor/install.sh first." >&2
  exit 1
fi

echo "Starting Azurite storage emulator..."
nohup azurite \
  --silent \
  --location "$AZURITE_DIR" \
  --blobHost 0.0.0.0 --blobPort "$BLOB_PORT" \
  --queueHost 0.0.0.0 --queuePort "$QUEUE_PORT" \
  --tableHost 0.0.0.0 --tablePort "$TABLE_PORT" \
  >"$AZURITE_LOG" 2>&1 &

# Wait for readiness (up to ~30s) so downstream consumers can rely on it.
for _ in $(seq 1 30); do
  if port_open "$BLOB_PORT"; then
    echo "Azurite ready (blob:$BLOB_PORT queue:$QUEUE_PORT table:$TABLE_PORT). Logs: $AZURITE_LOG"
    exit 0
  fi
  sleep 1
done

echo "Azurite did not become ready in time; see $AZURITE_LOG" >&2
exit 1

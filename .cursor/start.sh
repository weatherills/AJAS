#!/usr/bin/env bash
# Per-boot startup for AJAS. Brings up the Azurite storage emulator (Azure
# Blob/Queue/Table) that the backend pipelines depend on. Idempotent: it will
# not start a second instance if one is already listening, and it returns once
# the emulator is ready.
set -euo pipefail

export PATH="$HOME/.npm-global/bin:$PATH"

# --- CodeSpring CLI auto-login (best effort) ---------------------------------
# Materialize CodeSpring credentials from the injected CODESPRING_API_KEY secret
# on every boot so new sessions can read the project Kanban without a manual
# `codespring auth login`. Done here (per-boot) rather than in install.sh so the
# secret is never baked into an environment snapshot. Never prints the key; all
# failures are swallowed so this can never block startup.
if [ -n "${CODESPRING_API_KEY:-}" ]; then
  (
    set +e
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    export CODESPRING_API_URL="${CODESPRING_API_URL:-https://server.codespring.app}"

    # Write the same credentials file the CLI persists after `auth login`
    # (its interactive login requires a TTY, which boot scripts do not have).
    python3 - <<'PYCS'
import json, os, pathlib
key = os.environ.get("CODESPRING_API_KEY", "")
if not key.startswith("csk_"):
    raise SystemExit(0)
home = pathlib.Path(os.path.expanduser("~")) / ".codespring"
home.mkdir(parents=True, exist_ok=True)
(home / "credentials.json").write_text(json.dumps({
    "type": "api-key",
    "apiKey": key,
    "apiUrl": os.environ.get("CODESPRING_API_URL", "https://server.codespring.app"),
}, indent=2))
PYCS

    # Link this repo to its CodeSpring project by matching the GitHub remote.
    # .codespring/config.json is gitignored, so this never dirties the tree.
    if command -v codespring >/dev/null 2>&1 && [ ! -f "$REPO_ROOT/.codespring/config.json" ]; then
      slug="$(git -C "$REPO_ROOT" config --get remote.origin.url 2>/dev/null \
        | sed -E 's#(git@|https?://)[^/:]+[:/]##; s#\.git$##')"
      project_id="$(codespring projects --json 2>/dev/null | REPO_SLUG="$slug" python3 -c '
import sys, os, json
slug = (os.environ.get("REPO_SLUG") or "").lower()
try:
    data = json.load(sys.stdin)
except Exception:
    raise SystemExit(0)
items = data.get("data", data) if isinstance(data, dict) else data
for p in (items or []):
    url = (p.get("githubRepoUrl") or "").rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    if slug and url.lower().endswith(slug):
        print(p.get("id", "")); break
')"
      if [ -n "$project_id" ]; then
        ( cd "$REPO_ROOT" && codespring init --project "$project_id" --force >/dev/null 2>&1 ) \
          && echo "CodeSpring: linked project $project_id"
      fi
    fi

    [ -f "$HOME/.codespring/credentials.json" ] \
      && echo "CodeSpring: CLI authenticated from CODESPRING_API_KEY."
  ) || true
fi

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

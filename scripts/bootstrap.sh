#!/usr/bin/env bash
# One-command local bootstrap + seed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

python -m pip install -q -r backend/requirements-dev.txt
(cd frontend && npm ci --prefer-offline --no-audit --no-fund)

cp -n backend/local.settings.json.example backend/local.settings.json 2>/dev/null || true

echo "Start backend:  cd backend && func start"
echo "Start frontend: cd frontend && npm run dev"
echo "Seed demo:      python scripts/seed_demo.py"
echo "CLI:            python scripts/ajas.py seed"

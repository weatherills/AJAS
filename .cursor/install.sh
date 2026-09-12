#!/usr/bin/env bash
# Idempotent dev-environment bootstrap for AJAS (AI Job Application System).
# Provisions the toolchain the Azure Functions (Python) backend and web
# frontend need. Safe to run repeatedly and against cached/partial state.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

NPM_GLOBAL_PREFIX="$HOME/.npm-global"
NPM_GLOBAL_BIN="$NPM_GLOBAL_PREFIX/bin"

# --- System packages ---------------------------------------------------------
# The base image ships python3 without the venv/ensurepip module. Install it so
# the Azure Functions Python worker can run from an isolated virtual env.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update -y
    sudo apt-get install -y --no-install-recommends python3-venv python3-pip
  else
    apt-get update -y
    apt-get install -y --no-install-recommends python3-venv python3-pip
  fi
fi

# --- npm global prefix -------------------------------------------------------
# The base image's node resolves through a wrapper that leaves npm's global
# prefix pointing at "/", which is not writable. Pin a user-writable prefix so
# global CLI installs land somewhere on PATH.
mkdir -p "$NPM_GLOBAL_PREFIX"
npm config set prefix "$NPM_GLOBAL_PREFIX"
export NPM_CONFIG_PREFIX="$NPM_GLOBAL_PREFIX"
export PATH="$NPM_GLOBAL_BIN:$PATH"

# Make the global bin discoverable in future interactive and login shells.
PATH_LINE='export PATH="$HOME/.npm-global/bin:$PATH"'
for profile in "$HOME/.bashrc" "$HOME/.profile"; do
  touch "$profile"
  grep -qxF "$PATH_LINE" "$profile" || printf '\n%s\n' "$PATH_LINE" >> "$profile"
done

# --- Azure Functions Core Tools v4 -------------------------------------------
# Local host runtime for developing/running Azure Functions.
if ! command -v func >/dev/null 2>&1; then
  npm install -g azure-functions-core-tools@4 --unsafe-perm true
fi

# --- Azurite -----------------------------------------------------------------
# Local emulator for Azure Blob/Queue/Table Storage used across the pipelines.
if ! command -v azurite >/dev/null 2>&1; then
  npm install -g azurite
fi

# --- CodeSpring CLI ----------------------------------------------------------
# Project-planning CLI used by the committed CodeSpring agent skills
# (.cursor/skills/). Authenticate per-VM with `codespring auth login` (browser
# OAuth) or, headless, `codespring auth login --api-key "$CODESPRING_API_KEY"`.
# A 401 from the CodeSpring API often means the account is out of tokens, not
# that the API key is invalid. Check billing before rotating the secret.
if ! command -v codespring >/dev/null 2>&1; then
  npm install -g @codespring-app/cli
fi

# --- Python backend ----------------------------------------------------------
# Azure Functions Python worker runs from a project virtual environment.
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null

# Backend dependencies (guarded: the repo is spec-only until features land).
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
fi
for req in backend/requirements.txt functions/requirements.txt api/requirements.txt; do
  [ -f "$req" ] && pip install -r "$req"
done

# --- Frontend ----------------------------------------------------------------
# Install web dependencies once a frontend workspace exists.
for pkg in frontend/package.json web/package.json ui/package.json; do
  if [ -f "$pkg" ]; then
    ( cd "$(dirname "$pkg")" && npm install )
  fi
done

echo "AJAS dev environment ready."
echo "  python : $(python --version 2>&1)  (venv: $REPO_ROOT/.venv)"
echo "  node   : $(node --version)"
echo "  func   : $(func --version)"
echo "  azurite: $(azurite --version 2>/dev/null || echo installed)"
echo "  codespring: $(codespring --version 2>/dev/null || echo installed)"

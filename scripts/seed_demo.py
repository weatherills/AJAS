#!/usr/bin/env python3
"""Seed the local AJAS demo via HTTP (in-memory stores)."""

from __future__ import annotations

import json
import os
import urllib.request

BASE = os.environ.get("AJAS_BASE_URL", "http://127.0.0.1:7071").rstrip("/")
TOKEN = os.environ.get("AJAS_TOKEN", "local-user")

HELP = """
AJAS local demo

1. Backend (from repo root):
     source /workspace/.venv/bin/activate
     cd backend && func start
   AUTH_MODE=dev accepts Authorization: Bearer local-user

2. Frontend:
     cd frontend && npm run dev
   Open http://localhost:3000  (Vite proxies /api → 127.0.0.1:7071)

3. Seed in-process demo rows:
     python scripts/seed_demo.py

4. First-run checklist is on the home page.
"""


def _post(path: str) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=b"{}",
        method="POST",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    try:
        body = _post("/api/v1/ops/seed")
    except OSError:
        print(HELP.strip())
        print("\nCould not reach the Functions host. Start `func start` then re-run this script.")
        return
    print(json.dumps(body, indent=2))
    print(HELP.strip())


if __name__ == "__main__":
    main()

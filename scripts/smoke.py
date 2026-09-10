#!/usr/bin/env python3
"""Post-deploy / local smoke. Set AJAS_BASE_URL (default http://127.0.0.1:7071)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("AJAS_BASE_URL", "http://127.0.0.1:7071").rstrip("/")
TOKEN = os.environ.get("AJAS_TOKEN", "local-user")


def get(path: str, auth: bool = True) -> tuple[int, dict | str]:
    headers = {"Accept": "application/json"}
    if auth:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(f"{BASE}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main() -> int:
    checks = [
        ("/api/health", False),
        ("/api/ready", False),
        ("/api/v1/settings", True),
        ("/api/v1/ops/slo", True),
        ("/api/v1/meta/pagination", True),
        ("/api/v1/auth/me", True),
        ("/api/v1/auth/config", False),
    ]
    failed = 0
    for path, auth in checks:
        status, body = get(path, auth=auth)
        ok = 200 <= status < 300
        print(f"{'ok' if ok else 'FAIL'} {status} {path}")
        if not ok:
            print(body)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

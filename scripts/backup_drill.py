#!/usr/bin/env python3
"""Write a restore-drill log. Hits /api/health and /api/ready when the host is up."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ops" / "restore-drills.log"


def _get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            raw = resp.read()
            body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            return int(getattr(resp, "status", 200)), body if isinstance(body, dict) else {}
    except urllib.error.HTTPError as exc:
        return int(exc.code), {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def main() -> None:
    base = (os.environ.get("AJAS_BASE_URL") or "http://127.0.0.1:7071").rstrip("/")
    health_code, health = _get(f"{base}/api/health")
    ready_code, ready = _get(f"{base}/api/ready")
    cosmos = bool((os.environ.get("COSMOS_CONNECTION_STRING") or "").strip())
    storage = health.get("storage") or ("cosmos" if cosmos else "memory")
    ok = health_code == 200 and ready_code == 200 and bool(ready.get("ready") or health.get("status") == "ok")
    if health_code == 0:
        result = "skipped-host-down"
        notes = f"could not reach {base}/api/health; logged {storage} mode"
        ok = True
    else:
        result = "ok" if ok else "failed"
        notes = f"GET /api/health={health_code} GET /api/ready={ready_code} storage={storage}"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp} operator=local drill={'cosmos' if cosmos else 'memory-seed'} result={result} notes={notes}\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as handle:
        handle.write(line)
    print(f"Logged restore drill to {OUT}")
    if result == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

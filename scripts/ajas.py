#!/usr/bin/env python3
"""AJAS operator CLI: ingest, reindex, backfill, seed, adapters."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(script: str, extra: list[str] | None = None) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / script), *(extra or [])]
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="AJAS Sprint 12 operator CLI")
    parser.add_argument("command", choices=["ingest", "reindex", "backfill", "seed", "adapters", "help"])
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "help":
        print("commands: ingest reindex backfill seed adapters")
        return 0
    mapping = {
        "ingest": "verify_adapters.py",
        "reindex": "reindex_embeddings.py",
        "backfill": "renormalize.py",
        "seed": "seed_demo.py",
        "adapters": "verify_adapters.py",
    }
    script = mapping[args.command]
    extra = args.rest
    if args.command in {"ingest", "adapters"} and not extra:
        extra = ["greenhouse"]
    if args.command == "help":
        return 0
    print(json.dumps({"command": args.command, "script": script}))
    return _run(script, extra)


if __name__ == "__main__":
    raise SystemExit(main())

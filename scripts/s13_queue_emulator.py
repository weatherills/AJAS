#!/usr/bin/env python3
"""Local queue emulator for Sprint 13 workers (in-process, no Azure)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="AJAS local queue emulator")
    parser.add_argument("action", choices=["enqueue", "drain", "scripts"])
    parser.add_argument("--queue", default="ingest")
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()
    from app.sprint13.devex import drain_local, emulator_scripts, enqueue_local

    if args.action == "scripts":
        print(json.dumps(emulator_scripts()))
        return 0
    if args.action == "enqueue":
        payload = json.loads(args.payload)
        print(json.dumps(enqueue_local(args.queue, payload)))
        return 0
    print(json.dumps(drain_local(args.queue)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Export or import durable Cosmos containers as JSONL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="AJAS Cosmos backup")
    parser.add_argument("action", choices=("export", "import"))
    parser.add_argument("--dest", default="var/backup")
    args = parser.parse_args()

    from app.storage.backup import CRITICAL_CONTAINERS, export_backup, import_backup
    from app.storage.dal import CosmosDAL
    from app.storage.testing import FakeDatabase

    dest = Path(args.dest)
    live = bool((__import__("os").environ.get("COSMOS_CONNECTION_STRING") or "").strip())
    if live:
        from app.storage.cosmos import get_database

        dal = CosmosDAL(get_database())
    else:
        dal = CosmosDAL(FakeDatabase())
    if args.action == "export":
        counts = export_backup(dal, dest, containers=CRITICAL_CONTAINERS)
    else:
        counts = import_backup(dal, dest, containers=CRITICAL_CONTAINERS)
    print(json.dumps({"action": args.action, "dest": str(dest), "counts": counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

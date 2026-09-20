#!/usr/bin/env python3
"""Chunked Cosmos backfill with an RU budget (dry-run by default)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--container", default="matches")
    parser.add_argument("--chunk", type=int, default=50)
    parser.add_argument("--ru-budget", type=float, default=400)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from app.storage.backfill import run_backfill
    from app.storage.dal import CosmosDAL
    from app.storage.testing import FakeDatabase

    dal = CosmosDAL(FakeDatabase())

    def mutate(row: dict) -> dict:
        row.setdefault("schemaVersion", 1)
        return row

    result = run_backfill(
        dal,
        args.container,
        mutate,
        chunk_size=args.chunk,
        ru_budget=args.ru_budget,
        dry_run=not args.apply,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

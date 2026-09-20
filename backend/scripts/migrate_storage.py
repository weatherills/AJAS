#!/usr/bin/env python3
"""Apply Cosmos container + stored-logic migrations (expand-only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    from app.storage.migrate import apply_migrations, migration_plan
    from app.storage.testing import FakeDatabase

    live = bool((__import__("os").environ.get("COSMOS_CONNECTION_STRING") or "").strip() or (__import__("os").environ.get("COSMOS_ENDPOINT") or "").strip())
    if live:
        from app.storage.cosmos import get_database

        database = get_database()
    else:
        database = FakeDatabase()
    result = apply_migrations(database)
    result["plan"] = migration_plan()
    result["live"] = live
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

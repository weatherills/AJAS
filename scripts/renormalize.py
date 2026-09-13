#!/usr/bin/env python3
"""Bulk re-normalize stored jobs with current Sprint 11 rules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.job_sources.legacy_migrate import migrate_many  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    path = Path((argv or sys.argv)[1]) if (argv or sys.argv)[1:] else None
    rows = json.loads(path.read_text()) if path and path.exists() else []
    if isinstance(rows, dict):
        rows = rows.get("jobs") or rows.get("items") or []
    print(json.dumps(migrate_many(rows), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

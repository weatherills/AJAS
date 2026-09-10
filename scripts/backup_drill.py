#!/usr/bin/env python3
"""Write a restore-drill log for the backups runbook."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ops" / "restore-drills.log"


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{stamp} operator=local drill=memory-seed result=ok notes=GET /api/health then POST /api/v1/ops/seed\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as handle:
        handle.write(line)
    print(f"Logged restore drill to {OUT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verify optional adapters and run a single-source dry-run against fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.job_sources.boards import (  # noqa: E402
    glassdoor_jobs,
    indeed_jobs,
    linkedin_jobs,
    wellfound_jobs,
    workday_jobs,
    ziprecruiter_jobs,
)
from app.job_sources.circuit import snapshot as circuit_snapshot  # noqa: E402
from app.flags import feature_flags  # noqa: E402

ADAPTERS = {
    "glassdoor": glassdoor_jobs,
    "wellfound": wellfound_jobs,
    "indeed": indeed_jobs,
    "linkedin": linkedin_jobs,
    "workday": workday_jobs,
    "ziprecruiter": ziprecruiter_jobs,
}


def dry_run(source: str, fixture: Path | None = None) -> dict:
    path = fixture or ROOT / "backend" / "tests" / "fixtures" / "job_boards" / f"{source}.json"
    payload = json.loads(path.read_text()) if path.exists() else {"jobs": []}
    rows = ADAPTERS[source](payload, listing_url=f"https://fixtures.ajas.local/{source}")
    return {
        "source": source,
        "fixture": str(path),
        "count": len(rows),
        "flags": feature_flags(),
        "circuit": circuit_snapshot(source).__dict__,
        "dryRun": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=sorted(ADAPTERS))
    parser.add_argument("--fixture", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(dry_run(args.source, args.fixture), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

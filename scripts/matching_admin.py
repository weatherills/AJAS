#!/usr/bin/env python3
"""Admin helpers for match_records / match_evidence: provision, TTL, prune, rescore."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


def _store():
    from app.matching.records import get_record_store

    return get_record_store()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Matching records admin")
    parser.add_argument("command", choices=["containers", "indexes", "ttl", "prune", "rescore", "backfill", "telemetry"])
    parser.add_argument("--user", default="seed-user-001")
    parser.add_argument("--keep", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pairs", default="[]")
    args = parser.parse_args(argv)

    from app.matching.constants import EVIDENCE_TTL_DAYS, RECORDS_INDEXING, EVIDENCE_INDEXING
    from app.matching.containers import container_specs
    from app.storage.catalog import container_by_id

    if args.command == "containers":
        print(json.dumps([item["id"] for item in container_specs()], indent=2))
        return 0
    if args.command == "indexes":
        print(
            json.dumps(
                {
                    "match_records": RECORDS_INDEXING["compositeIndexes"],
                    "match_evidence": EVIDENCE_INDEXING["compositeIndexes"],
                },
                indent=2,
            )
        )
        return 0
    if args.command == "ttl":
        evidence = container_by_id("match_evidence")
        attempts = container_by_id("auto_apply_attempts")
        print(
            json.dumps(
                {
                    "match_evidenceDays": evidence.default_ttl // 86_400 if evidence.default_ttl else None,
                    "auto_apply_attemptsDays": attempts.default_ttl // 86_400 if attempts.default_ttl else None,
                    "specDays": EVIDENCE_TTL_DAYS,
                },
                indent=2,
            )
        )
        return 0
    store = _store()
    if args.command == "prune":
        print(json.dumps(store.prune(args.user, keep=args.keep, dry_run=args.dry_run), indent=2, default=str))
        return 0
    if args.command == "rescore":
        pairs = json.loads(args.pairs)
        print(json.dumps(store.batch_rescore(args.user, pairs), indent=2, default=str))
        return 0
    if args.command == "backfill":
        existing = store.list_records(args.user)
        pairs = [{"jobId": row["jobId"], "resumeId": row["resumeId"], "score": row.get("score") or 0} for row in existing]
        print(json.dumps(store.batch_rescore(args.user, pairs), indent=2, default=str))
        return 0
    print(json.dumps({"items": store.telemetry[-50:], "count": len(store.telemetry)}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

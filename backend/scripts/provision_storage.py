#!/usr/bin/env python3
"""Provision Cosmos containers, Blob containers, and Storage Queues.

Local (Azurite + Cosmos emulator):
  python backend/scripts/provision_storage.py --dry-run
  python backend/scripts/provision_storage.py --blobs --queues

Cloud (connection strings in env):
  COSMOS_CONNECTION_STRING=... python backend/scripts/provision_storage.py --cosmos --blobs --queues
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="AJAS storage provisioner")
    parser.add_argument("--cosmos", action="store_true", help="create Cosmos containers")
    parser.add_argument("--blobs", action="store_true", help="create Blob containers")
    parser.add_argument("--queues", action="store_true", help="create Storage Queues + poison queues")
    parser.add_argument("--all", action="store_true", help="cosmos + blobs + queues")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without calling Azure")
    parser.add_argument("--seed", action="store_true", help="upsert deterministic seed documents")
    parser.add_argument("--migrate", action="store_true", help="apply container + stored-logic migrations")
    args = parser.parse_args()

    live = args.cosmos or args.blobs or args.queues or args.all or args.migrate
    dry_run = args.dry_run or not live
    include_cosmos = args.all or args.cosmos or args.migrate or not live
    include_blobs = args.all or args.blobs or not live
    include_queues = args.all or args.queues or not live
    from app.storage.provision import cosmos_kwargs_preview, provision_all
    from app.storage.seeds import apply_seed, seed_documents

    result = provision_all(
        cosmos=include_cosmos,
        blobs=include_blobs,
        queues=include_queues,
        dry_run=dry_run,
    )
    result["cosmosPreview"] = cosmos_kwargs_preview()
    if args.seed:
        if dry_run:
            result["seeded"] = {key: len(rows) for key, rows in seed_documents().items()}
        else:
            from app.storage.cosmos import get_database
            from app.storage.dal import CosmosDAL

            result["seeded"] = apply_seed(CosmosDAL(get_database()))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

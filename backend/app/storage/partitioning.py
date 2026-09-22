"""Hot-partition review and synthetic keys for skewed Cosmos containers."""

from __future__ import annotations

import hashlib
from typing import Any

from app.storage.catalog import container_catalog

# Low-cardinality natural keys that would concentrate RU on a few partitions.
SKEW_WATCH: dict[str, str] = {
    "source_tenants": "source_id is greenhouse|lever — use synthetic_partition(source_id, tenant_key)",
    "vendor_field_mappings": "vendor is greenhouse|lever — bucket by vendor+field_key",
    "job_sources": "tiny catalog; full scan is cheaper than extra buckets",
    "weight_config": "global catalog; keep PK /weight_config_id",
}

SYNTHETIC_BUCKETS = 16


def synthetic_partition(natural: str, *parts: str, buckets: int = SYNTHETIC_BUCKETS) -> str:
    """Spread a low-cardinality key across N synthetic suffixes without changing the catalog PK."""
    payload = "|".join((natural, *parts))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % max(1, buckets)
    return f"{natural}:{bucket:02d}"


def partition_review() -> dict[str, Any]:
    rows = []
    for spec in container_catalog():
        pk = spec.partition_key
        skew = SKEW_WATCH.get(spec.id)
        rows.append(
            {
                "id": spec.id,
                "partitionKey": pk,
                "userScoped": pk in {"/user_id", "/userId"},
                "pointReadFriendly": pk in {"/id", "/user_id", "/userId", "/match_id"},
                "skewRisk": bool(skew),
                "guidance": skew or "Keep queries in-partition; do not cross-partition list.",
                "synthetic": synthetic_partition(spec.id) if skew else None,
            }
        )
    return {
        "schema": "ajas.cosmos.partition.review.v1",
        "buckets": SYNTHETIC_BUCKETS,
        "skewWatch": list(SKEW_WATCH),
        "containers": rows,
    }

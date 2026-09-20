"""Privacy-safe analytics export of durable Cosmos records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.storage.backup import DURABLE_CONTAINERS, dump_jsonl, export_container
from app.storage.pii import mask_value, redact

ANALYTICS_CONTAINERS: tuple[str, ...] = (
    "matches",
    "auto_apply_attempts",
    "decision_events",
    "job_postings_canonical",
    "event_log",
)


def _mask_emails(value: Any) -> Any:
    if isinstance(value, str) and "@" in value:
        return mask_value(value)
    if isinstance(value, list):
        return [_mask_emails(item) for item in value]
    if isinstance(value, dict):
        return {key: _mask_emails(item) for key, item in value.items()}
    return value


def scrub_row(container: str, row: dict[str, Any]) -> dict[str, Any]:
    clean = redact(container, row)
    clean.pop("_etag", None)
    clean.pop("etag", None)
    return _mask_emails(clean)


def export_analytics(dal: Any, dest: Path, *, containers: tuple[str, ...] | None = None) -> dict[str, int]:
    dest.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name in containers or ANALYTICS_CONTAINERS:
        rows = [scrub_row(name, row) for row in export_container(dal, name)]
        counts[name] = dump_jsonl(dest / f"{name}.jsonl", rows)
    return counts


def warehouse_contract() -> dict[str, Any]:
    return {
        "schema": "ajas.analytics.export.v1",
        "cadence": "nightly",
        "containers": list(ANALYTICS_CONTAINERS),
        "pii": "masked-or-redacted",
        "sourceOfTruth": DURABLE_CONTAINERS,
    }

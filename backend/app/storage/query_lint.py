"""Lint Cosmos queries so accidental cross-partition scans fail closed."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import get_settings
from app.storage.catalog import container_by_id

# Tiny catalogs that are meant to be scanned (few documents).
SCAN_ALLOWLIST = frozenset(
    {"job_sources", "email_templates", "model_registry", "schema_migrations", "vendor_field_mappings", "weight_config"}
)

_PROFILES: list[dict[str, Any]] = []


class CrossPartitionScanError(ValueError):
    """Query would fan out across partitions without an explicit allow."""


@dataclass
class LintResult:
    ok: bool
    cross_partition: bool
    reason: str
    container: str
    query: str
    tips: tuple[str, ...] = field(default_factory=tuple)


def reset_profiles() -> None:
    _PROFILES.clear()


def record_profile(container: str, query: str, *, ru: float, partition_key: Any | None) -> dict[str, Any]:
    row = {
        "container": container,
        "query": query,
        "ru": float(ru),
        "partitioned": partition_key is not None,
    }
    _PROFILES.append(row)
    return row


def top_queries(n: int = 5) -> list[dict[str, Any]]:
    ranked = sorted(_PROFILES, key=lambda row: row["ru"], reverse=True)
    return ranked[: max(1, n)]


def lint_query(
    container: str,
    query: str,
    *,
    partition_key: Any | None = None,
    allow_cross_partition: bool = False,
    strict: bool | None = None,
) -> LintResult:
    pk_path = container_by_id(container).partition_key
    pk_name = pk_path.lstrip("/")
    cross = partition_key is None
    if not cross:
        return LintResult(True, False, "in-partition", container, query)
    if container in SCAN_ALLOWLIST or allow_cross_partition:
        return LintResult(
            True,
            True,
            "allowlisted cross-partition",
            container,
            query,
            ("Keep allowlisted scans on tiny catalogs only.",),
        )
    tips = (
        f"Filter on partition key {pk_path} (field {pk_name}).",
        "Pass partition_key= to CosmosDAL.query.",
        "Add a composite index if the filter is a range on a hot path.",
    )
    enabled = get_settings().cosmos_query_strict if strict is None else strict
    return LintResult(not enabled, True, "cross-partition scan", container, query, tips)


def enforce_lint(result: LintResult) -> None:
    if not result.ok:
        raise CrossPartitionScanError(f"{result.container}: {result.reason}. " + " ".join(result.tips))

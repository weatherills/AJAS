"""Export / import durable Cosmos containers as JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

DURABLE_CONTAINERS: tuple[str, ...] = (
    "users",
    "resumes",
    "job_postings_canonical",
    "auto_apply_attempts",
    "matches",
    "decision_events",
    "user_settings",
    "settings_audit_log",
    "email_accounts",
    "email_threads",
)

CRITICAL_CONTAINERS: tuple[str, ...] = (
    "auto_apply_attempts",
    "matches",
    "decision_events",
    "user_settings",
    "settings_audit_log",
)


def export_container(dal: Any, container: str) -> list[dict[str, Any]]:
    page = dal.query(container, "SELECT * FROM c", max_items=100)
    rows = list(page.items)
    token = page.continuation
    while token:
        page = dal.query(container, "SELECT * FROM c", continuation=token, max_items=100)
        rows.extend(page.items)
        token = page.continuation
    return rows


def dump_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, default=str) + "\n")
            count += 1
    return count


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def export_backup(dal: Any, dest: Path, *, containers: tuple[str, ...] | None = None) -> dict[str, int]:
    dest.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name in containers or DURABLE_CONTAINERS:
        rows = export_container(dal, name)
        counts[name] = dump_jsonl(dest / f"{name}.jsonl", rows)
    (dest / "manifest.json").write_text(
        json.dumps({"containers": counts, "critical": list(CRITICAL_CONTAINERS)}, indent=2),
        encoding="utf-8",
    )
    return counts


def import_backup(dal: Any, src: Path, *, containers: tuple[str, ...] | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in containers or DURABLE_CONTAINERS:
        rows = load_jsonl(src / f"{name}.jsonl")
        for row in rows:
            dal.upsert(name, row)
        counts[name] = len(rows)
    return counts

"""Batch database writes for ingestion rows and logs."""

from __future__ import annotations

from typing import Any, Callable

WriteFn = Callable[[list[dict[str, Any]]], None]


def flush_batches(rows: list[dict[str, Any]], *, size: int = 50, writer: WriteFn | None = None) -> dict[str, int]:
    batches = [rows[i : i + size] for i in range(0, len(rows), size)] if rows else []
    written = 0
    for batch in batches:
        if writer:
            writer(batch)
        written += len(batch)
    return {"batches": len(batches), "written": written, "size": size}


def write_logs_and_matches(
    *,
    logs: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    size: int = 50,
    writer: WriteFn | None = None,
) -> dict[str, int]:
    tagged = [{**row, "kind": "log"} for row in logs] + [{**row, "kind": "match"} for row in matches]
    result = flush_batches(tagged, size=size, writer=writer)
    result["logs"] = len(logs)
    result["matches"] = len(matches)
    return result

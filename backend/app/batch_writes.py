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

"""Per-source usage, error, and cap dashboard counters."""

from __future__ import annotations

from collections import defaultdict


_STATS: dict[str, dict[str, int]] = defaultdict(lambda: {"fetched": 0, "errors": 0, "capped": 0})


def record(source: str, *, fetched: int = 0, errors: int = 0, capped: int = 0) -> dict[str, int]:
    row = _STATS[source]
    row["fetched"] += fetched
    row["errors"] += errors
    row["capped"] += capped
    return dict(row)


def dashboard() -> list[dict[str, object]]:
    rows = []
    for source, stats in sorted(_STATS.items()):
        cap_hit = stats["capped"] > 0
        rows.append({"source": source, **stats, "capHit": cap_hit})
    return rows


def reset() -> None:
    _STATS.clear()

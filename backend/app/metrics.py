"""In-app metrics snapshots for Grafana-style charts."""

from __future__ import annotations

from collections import defaultdict

_counters: dict[str, float] = defaultdict(float)


def increment(name: str, value: float = 1.0) -> None:
    _counters[name] += value


def reset() -> None:
    _counters.clear()


def snapshot() -> dict[str, object]:
    ingest = _counters.get("ingest.jobs", 0)
    match = _counters.get("match.compute", 0)
    apply = _counters.get("apply.submit", 0)
    errors = _counters.get("errors", 0)
    return {
        "series": [
            {"name": "Ingestion", "value": ingest, "color": "#38bdf8"},
            {"name": "Matches", "value": match, "color": "#34d399"},
            {"name": "Applies", "value": apply, "color": "#fbbf24"},
            {"name": "Errors", "value": errors, "color": "#f87171"},
        ],
        "counters": dict(_counters),
    }

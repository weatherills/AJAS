"""Pipeline SLO error budgets for ingest / match / apply."""

from __future__ import annotations

from collections import defaultdict

BUDGETS = {
    "ingest": {"availability": 0.995, "latencyMs": 8000},
    "match": {"availability": 0.99, "latencyMs": 800},
    "apply": {"availability": 0.99, "latencyMs": 30000},
}

_EVENTS: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "err": 0})


def record(pipeline: str, *, ok: bool) -> None:
    _EVENTS[pipeline]["ok" if ok else "err"] += 1


def snapshot() -> list[dict[str, object]]:
    rows = []
    for name, budget in BUDGETS.items():
        stats = _EVENTS[name]
        total = stats["ok"] + stats["err"]
        avail = (stats["ok"] / total) if total else 1.0
        remaining = max(0.0, avail - (1.0 - budget["availability"]))
        rows.append(
            {
                "pipeline": name,
                "availability": round(avail, 4),
                "budget": budget["availability"],
                "errorBudgetRemaining": round(remaining, 4),
                "ok": stats["ok"],
                "err": stats["err"],
                "healthy": avail >= budget["availability"] or total == 0,
            }
        )
    return rows


def reset() -> None:
    _EVENTS.clear()

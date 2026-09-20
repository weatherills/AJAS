"""Pipeline SLO error budgets for ingest / match / apply."""

from __future__ import annotations

from collections import defaultdict

BUDGETS = {
    "ingest": {"availability": 0.995, "latencyMs": 8000},
    "match": {"availability": 0.99, "latencyMs": 800},
    "apply": {"availability": 0.99, "latencyMs": 30000},
}

_EVENTS: dict[str, dict[str, int]] = defaultdict(lambda: {"ok": 0, "err": 0, "latencyP95": 0})


def record(pipeline: str, *, ok: bool, latency_ms: int | None = None) -> None:
    _EVENTS[pipeline]["ok" if ok else "err"] += 1
    if latency_ms is not None:
        current = _EVENTS[pipeline]["latencyP95"]
        _EVENTS[pipeline]["latencyP95"] = max(current, int(latency_ms))


def snapshot() -> list[dict[str, object]]:
    rows = []
    for name, budget in BUDGETS.items():
        stats = _EVENTS[name]
        total = stats["ok"] + stats["err"]
        avail = (stats["ok"] / total) if total else 1.0
        remaining = max(0.0, avail - (1.0 - budget["availability"]))
        p95 = int(stats.get("latencyP95") or 0)
        rows.append(
            {
                "pipeline": name,
                "availability": round(avail, 4),
                "budget": budget["availability"],
                "latencyMs": budget["latencyMs"],
                "latencyP95Ms": p95,
                "errorBudgetRemaining": round(remaining, 4),
                "ok": stats["ok"],
                "err": stats["err"],
                "healthy": (avail >= budget["availability"] or total == 0)
                and (p95 == 0 or p95 <= budget["latencyMs"]),
            }
        )
    return rows


def reset() -> None:
    _EVENTS.clear()

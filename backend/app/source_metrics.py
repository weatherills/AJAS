"""Per-source success / latency histograms for adapter fetches."""

from __future__ import annotations

from collections import defaultdict

BUCKETS = (50, 100, 250, 500, 1000, 2500, 5000)

_SAMPLES: dict[str, list[tuple[bool, float]]] = defaultdict(list)


def reset() -> None:
    _SAMPLES.clear()


def observe(source: str, *, ok: bool, latency_ms: float) -> None:
    _SAMPLES[source].append((ok, float(latency_ms)))


def histogram(source: str) -> dict[str, object]:
    rows = _SAMPLES.get(source) or []
    counts = {f"le_{bucket}": 0 for bucket in BUCKETS}
    counts["inf"] = 0
    ok = 0
    for success, ms in rows:
        if success:
            ok += 1
        placed = False
        for bucket in BUCKETS:
            if ms <= bucket:
                counts[f"le_{bucket}"] += 1
                placed = True
                break
        if not placed:
            counts["inf"] += 1
    return {"source": source, "count": len(rows), "ok": ok, "buckets": counts}

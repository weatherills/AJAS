"""In-process latency samples and p95 SLO budgets for key HTTP routes."""

from __future__ import annotations

from collections import defaultdict

BUDGETS_MS: dict[str, int] = {
    "POST /v1/matches/compute": 800,
    "POST /v1/matches/rank": 2500,
    "GET /v1/matches": 400,
    "GET /v1/jobs": 600,
    "POST /v1/matches/warmup": 400,
}

MAX_SAMPLES = 500
_latencies: dict[str, list[float]] = defaultdict(list)


def record_latency(route: str, elapsed_ms: float) -> None:
    bucket = _latencies[route]
    bucket.append(float(elapsed_ms))
    overflow = len(bucket) - MAX_SAMPLES
    if overflow > 0:
        del bucket[:overflow]


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return round(ordered[index], 1)


def snapshot() -> dict:
    routes = []
    alerts = []
    for route, budget in BUDGETS_MS.items():
        samples = list(_latencies.get(route, []))
        value = p95(samples)
        ok = value is None or value <= budget
        item = {
            "route": route,
            "budgetMs": budget,
            "p95Ms": value,
            "samples": len(samples),
            "ok": ok,
        }
        routes.append(item)
        if value is not None and not ok:
            alerts.append({"route": route, "p95Ms": value, "budgetMs": budget})
    return {"slo": routes, "alerts": alerts, "fallbackAlertPct": 5.0}

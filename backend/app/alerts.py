"""Adaptive alert thresholds that dampen noisy spikes."""

from __future__ import annotations

from collections import deque

_windows: dict[str, deque[float]] = {}


def observe(metric: str, value: float, *, window: int = 20) -> dict[str, object]:
    bucket = _windows.setdefault(metric, deque(maxlen=window))
    bucket.append(float(value))
    mean = sum(bucket) / len(bucket)
    variance = sum((item - mean) ** 2 for item in bucket) / len(bucket)
    stdev = variance ** 0.5
    threshold = mean + max(1.0, 2.0 * stdev)
    noisy = len(bucket) >= 5 and abs(value - mean) < 0.5 * max(1.0, stdev)
    alert = value >= threshold and not noisy
    return {
        "metric": metric,
        "value": value,
        "mean": round(mean, 3),
        "threshold": round(threshold, 3),
        "alert": alert,
        "damped": noisy and value >= threshold,
    }

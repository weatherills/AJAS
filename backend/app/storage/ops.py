"""Operational metrics and alert thresholds for Cosmos, queues, and blobs."""

from __future__ import annotations

from typing import Any

from app.metrics import snapshot as metrics_snapshot
from app.storage.blob_layout import blob_container_names
from app.storage.queue_schemas import all_queue_names, poison_queue_name, queue_names

ALERT_THRESHOLDS: dict[str, float] = {
    "cosmos.ru_per_sec": 4000,
    "cosmos.throttles": 5,
    "cosmos.latency_ms": 250,
    "cosmos.daily_ru": 250_000,
    "queue.depth": 500,
    "queue.dlq_depth": 1,
    "blob.bytes": float(50 * 1024 * 1024 * 1024),
}


def _counters() -> dict[str, float]:
    snap = metrics_snapshot()
    raw = snap.get("counters") if isinstance(snap, dict) else {}
    return {str(key): float(value) for key, value in (raw or {}).items()}


def storage_snapshot(
    *,
    queue_depths: dict[str, int] | None = None,
    blob_bytes: dict[str, int] | None = None,
    ru_per_sec: float | None = None,
    window_seconds: float = 60.0,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    counters = _counters()
    ru = float(counters.get("cosmos.ru") or 0)
    throttles = float(counters.get("cosmos.throttles") or 0)
    ops = float(counters.get("cosmos.ops") or 0)
    derived_ru = ru / window_seconds if ru_per_sec is None else float(ru_per_sec)
    latency = float(latency_ms if latency_ms is not None else counters.get("cosmos.latency_ms") or 0)
    depths = {name: int((queue_depths or {}).get(name, 0)) for name in queue_names()}
    poison = {
        poison_queue_name(name): int((queue_depths or {}).get(poison_queue_name(name), 0)) for name in queue_names()
    }
    blobs = {name: int((blob_bytes or {}).get(name, 0)) for name in blob_container_names()}
    dlq_depth = sum(poison.values())
    return {
        "schema": "ajas.storage.ops.v1",
        "cosmos": {
            "ru": ru,
            "ruPerSec": derived_ru,
            "throttles": throttles,
            "ops": ops,
            "latencyMs": latency,
        },
        "queues": {
            "depths": depths,
            "poison": poison,
            "maxDepth": max(depths.values()) if depths else 0,
            "dlqDepth": dlq_depth,
        },
        "blobs": {"bytes": blobs, "totalBytes": sum(blobs.values())},
        "thresholds": dict(ALERT_THRESHOLDS),
        "queueNames": list(all_queue_names()),
    }


def evaluate_alerts(snapshot: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    snap = snapshot or storage_snapshot()
    alerts: list[dict[str, Any]] = []
    cosmos = snap.get("cosmos") or {}
    if float(cosmos.get("ruPerSec") or 0) >= ALERT_THRESHOLDS["cosmos.ru_per_sec"]:
        alerts.append(_alert("cosmos.ru_per_sec", cosmos.get("ruPerSec"), "RU/s above provisioned budget"))
    if float(cosmos.get("throttles") or 0) >= ALERT_THRESHOLDS["cosmos.throttles"]:
        alerts.append(_alert("cosmos.throttles", cosmos.get("throttles"), "Cosmos 429 throttling"))
    if float(cosmos.get("latencyMs") or 0) >= ALERT_THRESHOLDS["cosmos.latency_ms"]:
        alerts.append(_alert("cosmos.latency_ms", cosmos.get("latencyMs"), "Cosmos request latency"))
    queues = snap.get("queues") or {}
    if float(queues.get("maxDepth") or 0) >= ALERT_THRESHOLDS["queue.depth"]:
        alerts.append(_alert("queue.depth", queues.get("maxDepth"), "Queue backlog"))
    if float(queues.get("dlqDepth") or 0) >= ALERT_THRESHOLDS["queue.dlq_depth"]:
        alerts.append(_alert("queue.dlq_depth", queues.get("dlqDepth"), "Poison / DLQ growth"))
    blobs = snap.get("blobs") or {}
    if float(blobs.get("totalBytes") or 0) >= ALERT_THRESHOLDS["blob.bytes"]:
        alerts.append(_alert("blob.bytes", blobs.get("totalBytes"), "Blob storage growth"))
    daily = float((snap.get("cosmos") or {}).get("dailyRu") or 0)
    if daily and daily >= ALERT_THRESHOLDS["cosmos.daily_ru"]:
        alerts.append(_alert("cosmos.daily_ru", daily, "Daily RU budget exhausted"))
    return alerts


def _alert(metric: str, value: Any, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "metric": metric,
        "value": value,
        "threshold": ALERT_THRESHOLDS[metric],
        "message": message,
        "channel": "#ajas-ops",
    }


def dashboard() -> dict[str, Any]:
    snap = storage_snapshot()
    alerts = evaluate_alerts(snap)
    return {"snapshot": snap, "alerts": alerts, "firing": bool(alerts)}

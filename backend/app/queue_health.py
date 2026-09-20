"""Detect stuck queue jobs and requeue them."""

from __future__ import annotations

from dataclasses import dataclass
from time import time


@dataclass
class QueueJob:
    id: str
    queue: str
    started_at: float
    attempts: int = 0
    status: str = "running"


def detect_stuck(jobs: list[QueueJob], *, now: float | None = None, timeout_sec: float = 300) -> list[QueueJob]:
    clock = now if now is not None else time()
    return [job for job in jobs if job.status == "running" and clock - job.started_at >= timeout_sec]


def requeue(jobs: list[QueueJob], *, now: float | None = None, timeout_sec: float = 300, max_attempts: int = 5) -> dict:
    stuck = detect_stuck(jobs, now=now, timeout_sec=timeout_sec)
    retried = 0
    dead = 0
    for job in stuck:
        job.attempts += 1
        if job.attempts > max_attempts:
            job.status = "dead"
            dead += 1
        else:
            job.status = "queued"
            job.started_at = now if now is not None else time()
            retried += 1
    return {"stuck": len(stuck), "retried": retried, "dead": dead}


def snapshot(*, depths: dict[str, int] | None = None, dlq_depth: int = 0, jobs: list[QueueJob] | None = None) -> dict:
    from app.queue_backpressure import backpressure
    from app.storage.queue_schemas import poison_queue_name, queue_names

    depths = depths or {}
    queues = []
    for name in queue_names():
        depth = int(depths.get(name, 0))
        poison = int(depths.get(poison_queue_name(name), 0))
        pressure = backpressure(depth)
        queues.append(
            {
                "queue": name,
                "depth": depth,
                "poisonDepth": poison,
                "lag": depth,
                **pressure,
            }
        )
    stuck = detect_stuck(jobs or [])
    return {
        "schema": "ajas.queue.health.v1",
        "queues": queues,
        "dlqDepth": int(dlq_depth),
        "stuck": len(stuck),
        "maxDepth": max((row["depth"] for row in queues), default=0),
        "alerts": [
            row for row in queues if row["mode"] != "open" or row["poisonDepth"] > 0
        ],
    }

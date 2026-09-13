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

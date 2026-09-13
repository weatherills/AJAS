"""Disable noisy sources after repeated 5xx responses."""

from __future__ import annotations

import time
from dataclasses import dataclass

FAILURE_THRESHOLD = 5
OPEN_SECONDS = 300.0

_states: dict[str, "_Breaker"] = {}


@dataclass
class CircuitSnapshot:
    source: str
    failures: int
    open: bool
    disabled: bool
    remaining_seconds: float


@dataclass
class _Breaker:
    failures: int = 0
    open_until: float = 0.0


def _now() -> float:
    return time.monotonic()


def _breaker(source: str) -> _Breaker:
    key = (source or "").strip().lower() or "unknown"
    if key not in _states:
        _states[key] = _Breaker()
    return _states[key]


def reset(source: str | None = None) -> None:
    if source is None:
        _states.clear()
        return
    _states.pop((source or "").strip().lower(), None)


def is_open(source: str) -> bool:
    br = _breaker(source)
    if br.open_until <= 0:
        return False
    if _now() >= br.open_until:
        br.open_until = 0.0
        br.failures = 0
        return False
    return True


def allow(source: str) -> bool:
    return not is_open(source)


def record_status(source: str, status: int) -> CircuitSnapshot:
    br = _breaker(source)
    if 500 <= int(status) < 600:
        br.failures += 1
        if br.failures >= FAILURE_THRESHOLD:
            br.open_until = _now() + OPEN_SECONDS
    else:
        br.failures = 0
        br.open_until = 0.0
    return snapshot(source)


def snapshot(source: str) -> CircuitSnapshot:
    br = _breaker(source)
    remaining = max(0.0, br.open_until - _now()) if br.open_until else 0.0
    opened = remaining > 0
    return CircuitSnapshot(
        source=(source or "").strip().lower() or "unknown",
        failures=br.failures,
        open=opened,
        disabled=opened,
        remaining_seconds=round(remaining, 2),
    )

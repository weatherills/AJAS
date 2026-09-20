"""Inject Cosmos 429s and regional outages into DAL retries."""

from __future__ import annotations

from collections import deque
from typing import Any


class InjectedThrottle(Exception):
    status_code = 429


class InjectedOutage(Exception):
    status_code = 503


_PENDING: deque[BaseException] = deque()


def reset() -> None:
    _PENDING.clear()


def inject(*errors: BaseException) -> None:
    _PENDING.extend(errors)


def maybe_raise() -> None:
    if _PENDING:
        raise _PENDING.popleft()


def throttle(n: int = 1) -> None:
    inject(*[InjectedThrottle("throttled") for _ in range(n)])


def region_outage(n: int = 1) -> None:
    inject(*[InjectedOutage("region unavailable") for _ in range(n)])

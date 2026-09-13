"""Persist idempotency keys with a conflict log and TTL window."""

from __future__ import annotations

from dataclasses import dataclass
from time import time


@dataclass
class IdemRecord:
    key: str
    fingerprint: str
    created_at: float
    response: dict


_STORE: dict[str, IdemRecord] = {}
_CONFLICTS: list[dict] = []


def reset() -> None:
    _STORE.clear()
    _CONFLICTS.clear()


def remember(key: str, fingerprint: str, response: dict, *, now: float | None = None, ttl_sec: float = 86400) -> dict:
    clock = now if now is not None else time()
    expire_stale(now=clock, ttl_sec=ttl_sec)
    existing = _STORE.get(key)
    if existing and existing.fingerprint != fingerprint:
        conflict = {"key": key, "stored": existing.fingerprint, "incoming": fingerprint, "at": clock}
        _CONFLICTS.append(conflict)
        return {"status": "conflict", "conflict": conflict, "cached": existing.response}
    _STORE[key] = IdemRecord(key=key, fingerprint=fingerprint, created_at=clock, response=response)
    return {"status": "stored", "cached": response}


def expire_stale(*, now: float | None = None, ttl_sec: float = 86400) -> int:
    clock = now if now is not None else time()
    stale = [key for key, row in _STORE.items() if clock - row.created_at > ttl_sec]
    for key in stale:
        del _STORE[key]
    return len(stale)


def conflicts() -> list[dict]:
    return list(_CONFLICTS)
